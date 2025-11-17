#!/usr/bin/env python3
"""
대용량 파일 처리 시스템 테스트
"""

def create_large_test_file(filename: str, size_mb: int):
    """테스트용 대용량 파일 생성"""
    import os
    
    content = """
웅진 지식관리시스템 대용량 문서 테스트

이 문서는 대용량 파일 처리 성능을 테스트하기 위해 생성된 문서입니다.
웅진그룹의 지식관리시스템(WKMS)은 다양한 크기의 문서를 효율적으로 처리할 수 있어야 합니다.

주요 기능:
1. 대용량 파일 업로드 (최대 100MB)
2. 스트리밍 처리를 통한 메모리 최적화
3. 백그라운드 처리로 사용자 경험 개선
4. 적응적 청킹 전략으로 성능 최적화
5. 한국어 NLP 분석 및 벡터 임베딩

기술 스택:
- FastAPI: 고성능 웹 프레임워크
- asyncio: 비동기 처리
- kiwipiepy: 한국어 형태소 분석
- AWS Bedrock: AI 모델 서비스
- PostgreSQL + pgvector: 벡터 데이터베이스

성능 최적화:
- 파일 크기별 차등 처리 전략
- 메모리 사용량 실시간 모니터링
- 청크 단위 스트리밍 처리
- 백그라운드 태스크 활용

웅진그룹은 교육, 출판, 콘텐츠 분야의 선도기업으로서
지식관리시스템을 통해 조직의 지식 자산을 체계적으로 관리하고 있습니다.

""" * (size_mb * 100)  # 대략적으로 MB 크기 조절
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    actual_size = os.path.getsize(filename) / (1024 * 1024)
    print(f"테스트 파일 생성: {filename} ({actual_size:.1f}MB)")
    
    return filename

def test_file_size_limits():
    """파일 크기 제한 테스트"""
    import requests
    
    print("=== 파일 크기 제한 테스트 ===")
    
    try:
        response = requests.get("http://localhost:8000/api/documents/file-size-limits")
        if response.status_code == 200:
            limits = response.json()
            print("✅ 파일 크기 제한 조회 성공:")
            print(f"  최대 파일 크기: {limits['max_file_size_mb']:.0f}MB")
            print(f"  대용량 임계값: {limits['large_file_threshold_mb']}MB")
            print("  처리 전략:")
            for strategy, config in limits['recommendations']['processing_strategies'].items():
                print(f"    {strategy}: 청크크기 {config['chunk_size']}, 오버랩 {config['overlap']}")
        else:
            print(f"❌ 파일 크기 제한 조회 실패: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")

def test_processing_time_estimation():
    """처리 시간 예상 테스트"""
    print("\n=== 처리 시간 예상 테스트 ===")
    
    # 테스트 파일 생성
    test_files = [
        ("small_test.txt", 5),
        ("medium_test.txt", 25),
        ("large_test.txt", 60)
    ]
    
    for filename, size_mb in test_files:
        try:
            create_large_test_file(filename, size_mb)
            
            import requests
            
            with open(filename, 'rb') as f:
                files = {'file': (filename, f, 'text/plain')}
                response = requests.post(
                    "http://localhost:8000/api/documents/estimate-processing-time",
                    files=files
                )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {filename} 예상 처리 시간:")
                print(f"  크기: {result['file_size_mb']:.1f}MB")
                print(f"  전략: {result['strategy']}")
                print(f"  예상 시간: {result['estimated_time_seconds']:.1f}초")
                print(f"  백그라운드 처리: {'예' if result['requires_background'] else '아니오'}")
            else:
                print(f"❌ {filename} 예상 실패: {response.status_code}")
                
        except Exception as e:
            print(f"❌ {filename} 테스트 실패: {e}")
        
        finally:
            # 테스트 파일 정리
            try:
                import os
                os.remove(filename)
            except:
                pass

def test_large_file_upload():
    """대용량 파일 업로드 테스트"""
    print("\n=== 대용량 파일 업로드 테스트 ===")
    
    # 중간 크기 파일로 테스트 (너무 크면 시간 오래 걸림)
    test_filename = "large_upload_test.txt"
    
    try:
        create_large_test_file(test_filename, 25)  # 25MB 파일
        
        import requests
        
        with open(test_filename, 'rb') as f:
            files = {'file': (test_filename, f, 'text/plain')}
            print("대용량 파일 업로드 중...")
            
            response = requests.post(
                "http://localhost:8000/api/documents/large-file-upload",
                files=files,
                timeout=300  # 5분 타임아웃
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 대용량 파일 업로드 성공:")
            
            if "task_id" in result:
                print(f"  태스크 ID: {result['task_id']}")
                print(f"  상태: {result['status']}")
                print(f"  예상 시간: {result.get('estimated_time', 0):.1f}초")
                print(f"  상태 확인 URL: {result.get('check_url', '')}")
                
                # 상태 확인 테스트
                task_id = result['task_id']
                print("\n백그라운드 처리 상태 확인 중...")
                
                import time
                for i in range(10):  # 최대 10번 확인
                    time.sleep(3)
                    status_response = requests.get(
                        f"http://localhost:8000/api/documents/large-file-status/{task_id}"
                    )
                    
                    if status_response.status_code == 200:
                        status = status_response.json()
                        print(f"  상태: {status.get('status', 'unknown')}, 진행률: {status.get('progress', 0)}%")
                        
                        if status.get('status') in ['completed', 'failed']:
                            break
                    else:
                        print(f"  상태 조회 실패: {status_response.status_code}")
                        break
                        
            else:
                print("  즉시 처리 완료")
                print(f"  성공: {result.get('success', False)}")
                
        else:
            print(f"❌ 대용량 파일 업로드 실패: {response.status_code}")
            if response.text:
                print(f"  오류: {response.text}")
                
    except Exception as e:
        print(f"❌ 대용량 파일 업로드 테스트 실패: {e}")
        
    finally:
        # 테스트 파일 정리
        try:
            import os
            os.remove(test_filename)
        except:
            pass

if __name__ == "__main__":
    print("🧪 대용량 파일 처리 시스템 테스트 시작")
    print("=" * 50)
    
    test_file_size_limits()
    test_processing_time_estimation() 
    test_large_file_upload()
    
    print("\n✅ 모든 테스트 완료!")
