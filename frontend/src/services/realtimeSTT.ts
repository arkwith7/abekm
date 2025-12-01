import { useCallback, useEffect, useRef, useState } from 'react';
import { getApiUrl } from '../utils/apiConfig';

/*
 * 실시간 STT 서비스(프론트엔드)
 *
 * AWS Transcribe Streaming WebSocket 클라이언트
 */

/**
 * 실시간 음성→텍스트 변환 클라이언트
 * 
 * AWS Transcribe Streaming을 통한 실시간 STT
 */
export class RealtimeSTTClient {
  private ws: WebSocket | null = null;
  private mediaStream: MediaStream | null = null;
  private mediaRecorder: MediaRecorder | null = null;
  private audioContext: AudioContext | null = null;
  private audioSource: MediaStreamAudioSourceNode | null = null;
  private audioWorkletNode: AudioWorkletNode | null = null;
  private scriptProcessor: ScriptProcessorNode | null = null;
  private silentGainNode: GainNode | null = null;
  private audioSampleRate = 16000;
  private isConnected = false;
  private readonly desiredSampleRate = 16000;
  private readonly workletProcessorName = 'pcm-audio-worklet';
  private readonly supportsAudioWorklet = typeof AudioWorkletNode !== 'undefined';

  // 음량 임계값 (배경 잡음 필터링용)
  // [수정 1] 임계값을 낮춰서 작은 목소리나 숨소리도 '음성'으로 인식하게 함
  // 기존 0.001 -> 0.0002로 변경 (훨씬 더 둔감하게 설정하여 끊김 방지)
  private readonly energyThreshold = 0.0002;
  private silenceFrameCount = 0; // 연속 침묵 프레임 카운터
  private readonly maxSilenceFrames = 30; // 약 2초 침묵 후 필터링
  private chunkCount = 0; // 디버깅용 청크 카운터

  // Pre-roll 버퍼 (초기 발화 손실 방지)
  private preRollBuffer: Int16Array[] = []; // 연결 전 오디오 버퍼
  private readonly maxPreRollChunks = 40; // 최대 40개 청크 (약 2.5초) - 초기 지연 감소
  private preRollSendInterval: NodeJS.Timeout | null = null; // 버퍼 점진 전송 타이머

  // 자동 중지 기능 (연속 침묵 감지)
  private continuousSilenceCount = 0; // 연속 침묵 청크 카운터
  // [수정 2] 침묵 허용 시간을 5초에서 10초 이상으로 늘림
  // 기존 40 -> 80으로 변경 (약 10초 동안 말이 없어도 끊지 않음)
  private readonly autoStopSilenceThreshold = 80;
  private autoStopCallback: (() => void) | null = null; // 자동 중지 콜백

  /**
   * 실시간 STT 시작
   * 
   * @param onTranscript - 텍스트 수신 콜백 (text: string, isPartial: boolean) => void
   * @param onError - 에러 콜백
   * @param language - 언어 코드 (기본: ko-KR)
   * @param autoStop - 자동 중지 활성화 (3초 침묵 시 자동 종료, 기본: true)
   */
  async start(
    onTranscript: (text: string, isPartial: boolean, confidence?: number) => void,
    onError?: (error: string) => void,
    language: string = 'ko-KR',
    autoStop: boolean = true
  ): Promise<boolean> {
    // 자동 중지 콜백 설정
    if (autoStop) {
      this.autoStopCallback = () => {
        console.log('⏱️ [STT-CLIENT] 자동 중지: 3초 연속 침묵 감지');
        this.stop();
      };
    } else {
      this.autoStopCallback = null;
    }
    console.log('🚀 [STT-CLIENT] 실시간 STT 시작 요청', { language });

    try {
      // 1. 마이크 권한 요청 (배경 잡음 억제 강화)
      console.log('🎤 [STT-CLIENT] 마이크 권한 요청 중...');
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,  // 브라우저 기본 잡음 억제
          autoGainControl: true,   // 자동 음량 조절 (원거리 소리 증폭 방지)
          // 고급 설정 (브라우저가 지원하는 경우)
          // @ts-ignore
          voiceIsolation: true,    // 음성 격리 (최신 브라우저)
          // @ts-ignore
          googNoiseSuppression: true,  // Google Chrome 강화 잡음 억제
          // @ts-ignore
          googHighpassFilter: true,    // 저주파 잡음 제거
        } as MediaTrackConstraints
      });
      console.log('✅ [STT-CLIENT] 마이크 권한 획득 완료', {
        tracks: this.mediaStream.getTracks().length,
        audioTracks: this.mediaStream.getAudioTracks().length
      });

      // 2. 오디오 파이프라인 준비 (AudioWorklet 우선) - WebSocket 연결 전에 먼저 준비
      await this.prepareAudioPipeline();

      // AudioContext 즉시 resume (초기 발성 누락 방지)
      if (this.audioContext && this.audioContext.state === 'suspended') {
        console.log('🔊 [STT-CLIENT] AudioContext 사전 활성화 중...');
        await this.audioContext.resume();
        console.log('✅ [STT-CLIENT] AudioContext 사전 활성화 완료');
      }

      // 오디오 파이프라인 안정화 대기 (50ms)
      await new Promise(resolve => setTimeout(resolve, 50));

      // 3. WebSocket 연결
      const token = localStorage.getItem('ABEKM_token');
      const wsUrl = this.buildWebSocketUrl(token);

      console.log('🔌 [STT-CLIENT] WebSocket 연결 시도', {
        url: wsUrl.replace(/token=.+/, 'token=***'),
        hasToken: !!token,
        tokenLength: token?.length
      });

      this.ws = new WebSocket(wsUrl);
      console.log('⏳ [STT-CLIENT] WebSocket 객체 생성 완료, 연결 대기 중...');

      // WebSocket 연결 완료를 기다리기 위한 Promise
      let resolveConnection: ((value: boolean) => void) | null = null;
      let rejectConnection: ((error: Error) => void) | null = null;

      const connectionTimeout = setTimeout(() => {
        console.error('❌ [STT-CLIENT] WebSocket 연결 타임아웃 (10초)');
        if (rejectConnection) {
          rejectConnection(new Error('WebSocket 연결 타임아웃'));
          rejectConnection = null;
        }
      }, 10000);

      const connectionPromise = new Promise<boolean>((resolve, reject) => {
        resolveConnection = resolve;
        rejectConnection = reject;
      });

      // 3. WebSocket 이벤트 핸들러
      this.ws.onopen = () => {
        clearTimeout(connectionTimeout);
        console.log('✅ [STT-CLIENT] WebSocket 연결 성공 (OPEN)', {
          readyState: this.ws?.readyState,
          url: this.ws?.url.replace(/token=.+/, 'token=***')
        });

        // 스트리밍 시작 메시지
        const startMessage = {
          action: 'start',
          language: language,
          sample_rate: this.audioSampleRate
        };
        console.log('📤 [STT-CLIENT] 시작 메시지 전송', startMessage);
        this.ws?.send(JSON.stringify(startMessage));

        // 연결 성공 - Promise resolve는 'started' 메시지 수신 시
      };

      this.ws.onmessage = async (event) => {
        console.log('📥 [STT-CLIENT] 메시지 수신', {
          dataType: typeof event.data,
          dataLength: event.data.length
        });

        const data = JSON.parse(event.data);
        console.log('📦 [STT-CLIENT] 메시지 파싱 완료', { type: data.type, data });

        if (data.type === 'started') {
          console.log('✅ [STT-CLIENT] STT 세션 시작됨', {
            session_id: data.session_id,
            language: data.language,
            sample_rate: data.sample_rate
          });

          // AudioContext 재활성화 (브라우저 정책 대응)
          if (this.audioContext) {
            await this.audioContext.resume().catch((resumeError) => {
              console.warn('⚠️ [STT-CLIENT] AudioContext resume 실패', resumeError);
            });
          }

          // Pre-roll 버퍼 점진적 전송 (AWS가 warmup으로 인식하지 않도록)
          if (this.preRollBuffer.length > 0) {
            console.log(`🎬 [STT-CLIENT] Pre-roll 버퍼 점진 전송 시작 - ${this.preRollBuffer.length}개 청크`);

            // 버퍼를 복사 (전송 중 새로운 오디오가 추가되는 것 방지)
            const bufferToSend = [...this.preRollBuffer];
            this.preRollBuffer = []; // 버퍼 즉시 비우기

            // 점진적 전송 (20ms 간격으로 한 청크씩)
            let sentCount = 0;
            this.preRollSendInterval = setInterval(() => {
              if (sentCount < bufferToSend.length && this.ws?.readyState === WebSocket.OPEN) {
                try {
                  this.ws.send(bufferToSend[sentCount].buffer);
                  sentCount++;

                  if (sentCount % 10 === 0 || sentCount === bufferToSend.length) {
                    console.log(`📤 [STT-CLIENT] Pre-roll 전송 진행: ${sentCount}/${bufferToSend.length}`);
                  }
                } catch (error) {
                  console.warn('⚠️ [STT-CLIENT] Pre-roll 청크 전송 실패', error);
                }
              }

              // 전송 완료 또는 연결 끊김
              if (sentCount >= bufferToSend.length || this.ws?.readyState !== WebSocket.OPEN) {
                if (this.preRollSendInterval) {
                  clearInterval(this.preRollSendInterval);
                  this.preRollSendInterval = null;
                }
                console.log(`✅ [STT-CLIENT] Pre-roll 버퍼 전송 완료 (${sentCount}/${bufferToSend.length})`);

                // ✅ Pre-roll 전송 완료 후 실시간 오디오 전송 활성화
                this.isConnected = true;
                console.log('🎤 [STT-CLIENT] 실시간 오디오 스트리밍 시작');
              }
            }, 20); // 20ms 간격 (실시간 오디오와 비슷한 속도)
          } else {
            // 버퍼가 없으면 즉시 활성화
            this.isConnected = true;
            console.log('🎤 [STT-CLIENT] 실시간 오디오 스트리밍 시작');
          }

          // 짧은 대기 (AWS 처리 준비)
          await new Promise(resolve => setTimeout(resolve, 50));          // 연결 완료 시그널
          if (resolveConnection) {
            resolveConnection(true);
            resolveConnection = null;
          }
        } else if (data.type === 'transcript') {
          console.log('📝 [STT-CLIENT] 변환 결과 수신', {
            text: data.text,
            isPartial: data.is_partial,
            confidence: data.confidence,
            textLength: data.text.length
          });
          onTranscript(data.text, data.is_partial, data.confidence);
        } else if (data.type === 'error') {
          console.error('❌ [STT-CLIENT] 서버 오류 수신', { message: data.message });
          onError?.(data.message);
          this.stop();
        } else {
          console.warn('⚠️ [STT-CLIENT] 알 수 없는 메시지 타입', { type: data.type, data });
        }
      };

      this.ws.onerror = (error) => {
        clearTimeout(connectionTimeout);
        console.error('❌ [STT-CLIENT] WebSocket 오류 발생', {
          error,
          readyState: this.ws?.readyState,
          url: this.ws?.url.replace(/token=.+/, 'token=***')
        });
        if (rejectConnection) {
          rejectConnection(new Error('WebSocket 연결 실패'));
          rejectConnection = null;
        }
        onError?.('WebSocket 연결 실패');
        this.stop();
      };

      this.ws.onclose = (event) => {
        console.log('🔌 [STT-CLIENT] WebSocket 연결 종료', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          readyState: this.ws?.readyState
        });
        this.isConnected = false;
      };

      // WebSocket 연결 완료 대기
      console.log('⏳ [STT-CLIENT] WebSocket 연결 및 STT 세션 시작 대기 중...');
      const connected = await connectionPromise;

      console.log('✅ [STT-CLIENT] 실시간 STT 시작 완료 (연결 및 세션 시작 성공)');
      return connected;

    } catch (error: any) {
      console.error('❌ [STT-CLIENT] 실시간 STT 시작 실패', {
        error,
        message: error.message,
        name: error.name,
        stack: error.stack
      });
      this.stop();
      onError?.(error.message || '마이크 권한을 확인해주세요');
      return false;
    }
  }

  /**
   * 오디오 파이프라인 초기화 (AudioWorklet → ScriptProcessor 폴백)
   */
  private async prepareAudioPipeline() {
    console.log('🎤 [STT-AUDIO] 오디오 파이프라인 준비 시작');

    if (!this.mediaStream) {
      throw new Error('MediaStream이 없습니다. 마이크 권한을 확인하세요.');
    }

    this.teardownAudioPipeline();

    try {
      const AudioContextCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextCtor) {
        throw new Error('브라우저가 AudioContext를 지원하지 않습니다.');
      }

      this.audioContext = new AudioContextCtor({ sampleRate: this.desiredSampleRate }) as AudioContext;
      await this.audioContext.resume();
      this.audioSampleRate = this.audioContext.sampleRate;

      console.log('✅ [STT-AUDIO] AudioContext 준비 완료', {
        desiredSampleRate: this.desiredSampleRate,
        actualSampleRate: this.audioSampleRate,
        state: this.audioContext.state,
        workletSupported: this.supportsAudioWorklet && !!this.audioContext.audioWorklet
      });

      this.audioSource = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.silentGainNode = this.audioContext.createGain();
      this.silentGainNode.gain.value = 0;
      this.silentGainNode.connect(this.audioContext.destination);

      const workletReady = await this.setupAudioWorklet();
      if (!workletReady) {
        this.setupScriptProcessor();
      }

      console.log('✅ [STT-AUDIO] 오디오 파이프라인 준비 완료', {
        mode: workletReady ? 'audio-worklet' : 'script-processor',
        sampleRate: this.audioSampleRate
      });
    } catch (error) {
      console.error('❌ [STT-AUDIO] 오디오 파이프라인 준비 실패', error);
      throw error;
    }
  }

  private async setupAudioWorklet(): Promise<boolean> {
    if (!this.audioContext?.audioWorklet || !this.supportsAudioWorklet || !this.audioSource) {
      return false;
    }

    try {
      const moduleUrl = this.createWorkletModule();
      await this.audioContext.audioWorklet.addModule(moduleUrl);
      URL.revokeObjectURL(moduleUrl);

      this.audioWorkletNode = new AudioWorkletNode(this.audioContext, this.workletProcessorName);
      this.audioWorkletNode.port.onmessage = (event) => {
        const chunk = event.data as Float32Array;
        if (chunk) {
          this.handleFloat32Chunk(chunk);
        }
      };

      this.audioSource.connect(this.audioWorkletNode);
      if (this.silentGainNode) {
        this.audioWorkletNode.connect(this.silentGainNode);
      } else {
        this.audioWorkletNode.connect(this.audioContext.destination);
      }

      console.log('🎛️ [STT-AUDIO] AudioWorklet 활성화');
      return true;
    } catch (error) {
      console.warn('⚠️ [STT-AUDIO] AudioWorklet 초기화 실패, ScriptProcessor로 폴백', error);
      return false;
    }
  }

  private setupScriptProcessor() {
    if (!this.audioContext || !this.audioSource) {
      throw new Error('AudioContext 초기화 실패');
    }

    // 버퍼 크기를 2048로 줄여서 지연 시간 감소 (초기 발성 반응 속도 개선)
    this.scriptProcessor = this.audioContext.createScriptProcessor(2048, 1, 1);
    let chunksSent = 0;
    let warmupComplete = false;

    this.scriptProcessor.onaudioprocess = (event) => {
      const inputData = event.inputBuffer.getChannelData(0);

      if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
        // 워밍업: 연결 전에도 버퍼를 읽어서 오디오 파이프라인 활성화
        if (!warmupComplete) {
          warmupComplete = true;
          console.log('🔥 [STT-AUDIO] 오디오 파이프라인 워밍업 완료');
        }
        return;
      }

      chunksSent++;
      if (chunksSent === 1 || chunksSent % 50 === 0) {
        console.log(`📤 [STT-AUDIO] 오디오 청크 전송 #${chunksSent}`, {
          sampleCount: inputData.length,
          readyState: this.ws?.readyState
        });
      }

      const copyBuffer = new Float32Array(inputData.length);
      copyBuffer.set(inputData);
      this.handleFloat32Chunk(copyBuffer);
    };

    this.audioSource.connect(this.scriptProcessor);
    if (this.silentGainNode) {
      this.scriptProcessor.connect(this.silentGainNode);
    } else {
      this.scriptProcessor.connect(this.audioContext.destination);
    }

    console.log('🌀 [STT-AUDIO] ScriptProcessor 활성화 (폴백 모드)');
  }

  private handleFloat32Chunk(chunk: Float32Array) {
    // Float32 → Int16 변환 (PCM)
    const pcmData = new Int16Array(chunk.length);
    for (let i = 0; i < chunk.length; i++) {
      const s = Math.max(-1, Math.min(1, chunk[i]));
      pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // 연결 전: pre-roll 버퍼에 저장
    if (!this.isConnected || !this.ws || this.ws.readyState !== WebSocket.OPEN) {
      if (this.preRollBuffer.length < this.maxPreRollChunks) {
        this.preRollBuffer.push(pcmData);
        if (this.preRollBuffer.length === 1 || this.preRollBuffer.length % 10 === 0) {
          console.log(`📦 [STT-PREROLL] 버퍼링 중... ${this.preRollBuffer.length}/${this.maxPreRollChunks}개 청크`);
        }
      } else if (this.preRollBuffer.length === this.maxPreRollChunks) {
        // 버퍼가 가득 찬 경우: FIFO 방식으로 오래된 청크 제거하고 새 청크 추가
        this.preRollBuffer.shift(); // 가장 오래된 청크 제거
        this.preRollBuffer.push(pcmData); // 새 청크 추가
      }
      return;
    }

    // 연결됨: 실시간 전송
    this.chunkCount++;

    // 음량 체크 (디버깅용)
    const rmsEnergy = this.calculateRMS(chunk);
    if (this.chunkCount <= 10 || this.chunkCount % 100 === 0) {
      console.log(`🎵 [STT-AUDIO] 청크 #${this.chunkCount} RMS: ${rmsEnergy.toFixed(4)}, 임계값: ${this.energyThreshold}, 침묵카운트: ${this.silenceFrameCount}`);
    }

    // 에너지 임계값보다 낮으면 (배경 잡음/원거리 소리)
    if (rmsEnergy < this.energyThreshold) {
      this.silenceFrameCount++;
      this.continuousSilenceCount++;

      // 자동 중지 체크 (3초 연속 침묵)
      if (this.autoStopCallback && this.continuousSilenceCount >= this.autoStopSilenceThreshold) {
        console.log(`⏱️ [STT-AUDIO] 자동 중지 조건 충족: ${this.continuousSilenceCount}개 침묵 청크 (${(this.continuousSilenceCount * 128).toFixed(0)}ms)`);
        // 비동기 콜백 호출 (현재 오디오 처리 루프와 분리)
        setTimeout(() => {
          if (this.autoStopCallback) {
            this.autoStopCallback();
          }
        }, 0);
        return;
      }

      // 연속 침묵 프레임이 임계값을 초과하면 전송하지 않음
      if (this.silenceFrameCount > this.maxSilenceFrames) {
        if (this.silenceFrameCount === this.maxSilenceFrames + 1) {
          console.log(`🔇 [STT-AUDIO] 배경 잡음 필터링 시작 (RMS: ${rmsEnergy.toFixed(4)} < ${this.energyThreshold})`);
        }
        return; // 배경 잡음 필터링
      }
    } else {
      // 음성 감지 시 침묵 카운터 리셋
      if (this.silenceFrameCount > 0) {
        console.log(`🔊 [STT-AUDIO] 음성 감지! RMS: ${rmsEnergy.toFixed(4)}, 침묵카운트 리셋`);
      }
      this.silenceFrameCount = 0;
      this.continuousSilenceCount = 0; // 연속 침묵 카운터도 리셋
    }

    // 전송
    try {
      this.ws.send(pcmData.buffer);
    } catch (error) {
      console.error('❌ [STT-AUDIO] 오디오 청크 전송 실패', error);
    }
  }

  /**
   * RMS (Root Mean Square) 에너지 계산
   * 음량 측정을 위한 표준 방법
   */
  private calculateRMS(samples: Float32Array): number {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return Math.sqrt(sum / samples.length);
  }

  /**
   * AWS Transcribe 스트림 워밍업
   * 
   * 초기 발성 손실을 방지하기 위해 침묵 오디오 패킷을 먼저 전송하여
   * AWS의 VAD(Voice Activity Detection)와 네트워크 버퍼를 활성화
   */
  private async sendWarmupAudio() {
    // 워밍업은 isConnected 체크를 건너뜀 (연결 확정 전에 수행)
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('⚠️ [STT-WARMUP] WebSocket 미연결 - 워밍업 스킵');
      return;
    }

    // 500ms 분량의 침묵 오디오 생성 (16kHz = 8000 samples)
    const warmupSamples = 8000;
    const silenceBuffer = new Int16Array(warmupSamples);

    // 완전 침묵 대신 매우 작은 노이즈 추가 (VAD 활성화)
    for (let i = 0; i < warmupSamples; i++) {
      silenceBuffer[i] = Math.floor(Math.random() * 10 - 5); // -5 ~ +5 범위의 작은 노이즈
    }

    try {
      this.ws.send(silenceBuffer.buffer);
      console.log('✅ [STT-WARMUP] 워밍업 오디오 전송 완료', {
        samples: warmupSamples,
        duration: '500ms',
        bytes: silenceBuffer.buffer.byteLength
      });
    } catch (error) {
      console.error('❌ [STT-WARMUP] 워밍업 오디오 전송 실패', error);
    }
  }

  private createWorkletModule(): string {
    const workletCode = `class PCMWorkletProcessor extends AudioWorkletProcessor {
      process(inputs) {
        const input = inputs[0];
        if (!input || input.length === 0) return true;
        const channelData = input[0];
        if (!channelData || channelData.length === 0) return true;
        
        // 받은 그대로 전송 (버퍼링 없음)
        const copy = new Float32Array(channelData.length);
        copy.set(channelData);
        this.port.postMessage(copy);
        return true;
      }
    }
    registerProcessor('${this.workletProcessorName}', PCMWorkletProcessor);`;

    const blob = new Blob([workletCode], { type: 'application/javascript' });
    return URL.createObjectURL(blob);
  }

  private teardownAudioPipeline() {
    if (this.audioWorkletNode) {
      this.audioWorkletNode.port.onmessage = null;
      try {
        this.audioWorkletNode.disconnect();
      } catch (error) {
        console.warn('⚠️ [STT-AUDIO] AudioWorkletNode disconnect 실패', error);
      }
      this.audioWorkletNode = null;
    }

    if (this.scriptProcessor) {
      this.scriptProcessor.onaudioprocess = null as any;
      try {
        this.scriptProcessor.disconnect();
      } catch (error) {
        console.warn('⚠️ [STT-AUDIO] ScriptProcessor disconnect 실패', error);
      }
      this.scriptProcessor = null;
    }

    if (this.audioSource) {
      try {
        this.audioSource.disconnect();
      } catch (error) {
        console.warn('⚠️ [STT-AUDIO] AudioSource disconnect 실패', error);
      }
      this.audioSource = null;
    }

    if (this.silentGainNode) {
      try {
        this.silentGainNode.disconnect();
      } catch (error) {
        console.warn('⚠️ [STT-AUDIO] GainNode disconnect 실패', error);
      }
      this.silentGainNode = null;
    }

    if (this.audioContext) {
      this.audioContext.close().catch((error) => {
        console.warn('⚠️ [STT-AUDIO] AudioContext 종료 중 오류', error);
      });
      this.audioContext = null;
    }
  }

  /**
   * 실시간 STT 중지
   */
  stop() {
    console.log('🛑 [STT-CLIENT] 실시간 STT 중지 시작', {
      hasAudioContext: !!this.audioContext,
      hasMediaRecorder: !!this.mediaRecorder,
      hasMediaStream: !!this.mediaStream,
      hasWebSocket: !!this.ws,
      wsReadyState: this.ws?.readyState,
      isConnected: this.isConnected
    });

    // 침묵 카운터 및 청크 카운터 리셋
    this.silenceFrameCount = 0;
    this.chunkCount = 0;
    this.preRollBuffer = []; // Pre-roll 버퍼 초기화

    // Pre-roll 전송 타이머 정리
    if (this.preRollSendInterval) {
      clearInterval(this.preRollSendInterval);
      this.preRollSendInterval = null;
    }

    this.teardownAudioPipeline();

    // MediaRecorder 중지
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      console.log('⏹️ [STT-CLIENT] MediaRecorder 중지 중...');
      this.mediaRecorder.stop();
      this.mediaRecorder = null;
      console.log('✅ [STT-CLIENT] MediaRecorder 중지 완료');
    }

    // MediaStream 트랙 중지
    if (this.mediaStream) {
      const trackCount = this.mediaStream.getTracks().length;
      console.log(`🎤 [STT-CLIENT] MediaStream 트랙 중지 중... (${trackCount}개 트랙)`);
      this.mediaStream.getTracks().forEach(track => {
        console.log(`  - 트랙 중지: ${track.kind}, enabled: ${track.enabled}, readyState: ${track.readyState}`);
        track.stop();
      });
      this.mediaStream = null;
      console.log('✅ [STT-CLIENT] MediaStream 트랙 중지 완료');
    }

    // WebSocket 종료
    if (this.ws) {
      const currentReadyState = this.ws.readyState;
      console.log(`🔌 [STT-CLIENT] WebSocket 종료 중... (readyState: ${currentReadyState})`);

      if (this.ws.readyState === WebSocket.OPEN) {
        console.log('📤 [STT-CLIENT] 중지 메시지 전송 중...');
        this.ws.send(JSON.stringify({ action: 'stop' }));
        console.log('✅ [STT-CLIENT] 중지 메시지 전송 완료');

        // ✅ 서버의 응답 대기 (서버가 WebSocket 종료하면 onclose 이벤트 발생)
        // 즉시 close() 하지 않음 - 서버가 graceful shutdown 수행 후 종료
        console.log('⏳ [STT-CLIENT] 서버 종료 대기 중...');
      } else {
        console.warn(`⚠️ [STT-CLIENT] WebSocket이 OPEN 상태가 아님 - 중지 메시지 전송 불가 (readyState: ${currentReadyState})`);
        // WebSocket이 이미 종료된 경우 즉시 정리
        this.ws = null;
      }
    }

    this.isConnected = false;
    console.log('✅ [STT-CLIENT] 실시간 STT 중지 완료');
  }

  /**
   * 연결 상태 확인
   */
  isActive(): boolean {
    return this.isConnected && this.ws?.readyState === WebSocket.OPEN;
  }

  private buildWebSocketUrl(token: string | null): string {
    // 개발 환경: 백엔드로 직접 연결 (프록시 우회)
    // 프로덕션 환경: 기존 로직 사용
    if (process.env.NODE_ENV === 'development') {
      const backendWs = 'ws://localhost:8000';
      const query = token ? `?token=${encodeURIComponent(token)}` : '';
      return `${backendWs}/api/v1/transcribe/stream${query}`;
    }

    // 프로덕션: API URL 기반 WebSocket 경로 구성
    const apiBase = getApiUrl();
    const httpBase = apiBase && apiBase.length > 0 ? apiBase : `${window.location.origin}/api`;
    const normalizedBase = httpBase.replace(/\/$/, '');
    const wsBase = normalizedBase.replace(/^http/, 'ws');
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${wsBase}/v1/transcribe/stream${query}`;
  }
}

/**
 * 실시간 STT Hook (React)
 */
export const useRealtimeSTT = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [interimText, setInterimText] = useState('');
  const [finalText, setFinalText] = useState('');
  const [isSupported] = useState(() => {
    if (typeof window === 'undefined' || typeof navigator === 'undefined') {
      return false;
    }
    const hasMediaDevices = !!navigator.mediaDevices?.getUserMedia;
    const extendedWindow = window as Window & { webkitAudioContext?: typeof AudioContext };
    const hasAudioContext = typeof window.AudioContext !== 'undefined' || typeof extendedWindow.webkitAudioContext !== 'undefined';
    return hasMediaDevices && hasAudioContext;
  });
  const clientRef = useRef<RealtimeSTTClient | null>(null);
  const isMountedRef = useRef(true);

  // 컴포넌트 언마운트 시 cleanup
  const cleanup = useCallback(() => {
    if (clientRef.current) {
      console.log('🧹 [STT-HOOK] Cleanup - 기존 클라이언트 정리');
      clientRef.current.stop();
      clientRef.current = null;
    }
  }, []);

  // 언마운트 시 cleanup (useEffect는 StrictMode에서 2번 실행되므로 ref로 추적)
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  const startRecording = useCallback(async (language: string = 'ko-KR') => {
    // 이미 활성화된 클라이언트가 있으면 재사용
    if (clientRef.current?.isActive()) {
      console.warn('⚠️ [STT-HOOK] 이미 녹음 중입니다 - 기존 세션 재사용');
      return true;
    }

    if (!isSupported) {
      alert('이 브라우저에서는 실시간 음성인식을 지원하지 않습니다. 최신 브라우저를 사용해주세요.');
      return false;
    }

    // 기존 클라이언트 정리
    cleanup();

    console.log('🎬 [STT-HOOK] 새 STT 세션 시작', { language });
    const client = new RealtimeSTTClient();
    clientRef.current = client;

    setIsRecording(true);

    const success = await client.start(
      (text, isPartial, confidence) => {
        // 언마운트된 컴포넌트에서는 상태 업데이트 하지 않음
        if (!isMountedRef.current) {
          console.warn('⚠️ [STT-HOOK] 언마운트된 컴포넌트 - 상태 업데이트 스킵');
          return;
        }

        if (isPartial) {
          // 중간 결과 (회색으로 표시)
          setInterimText(text);
        } else {
          // 확정 결과
          setFinalText(prev => prev + ' ' + text);
          setInterimText('');
        }
      },
      (error) => {
        console.error('❌ [STT-HOOK] STT 오류:', error);
        if (isMountedRef.current) {
          setIsRecording(false);
          alert(error);
        }
      },
      language
    );

    if (!success) {
      if (isMountedRef.current) {
        setIsRecording(false);
      }
      clientRef.current = null;
    }

    return success;
  }, [isSupported, cleanup]);

  const stopRecording = useCallback(() => {
    console.log('🛑 [STT-HOOK] STT 중지 요청');
    cleanup();
    if (isMountedRef.current) {
      setIsRecording(false);
      setInterimText('');
    }
  }, [cleanup]);

  const reset = useCallback(() => {
    if (isMountedRef.current) {
      setFinalText('');
      setInterimText('');
    }
  }, []);

  return {
    isRecording,
    interimText,
    finalText,
    isSupported,
    startRecording,
    stopRecording,
    reset
  };
};
