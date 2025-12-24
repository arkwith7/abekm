import React, { useEffect, useMemo, useState } from 'react';
import { Database, Folder, Play, Settings as SettingsIcon, Clock, Tag } from 'lucide-react';
import {
  getMyContainers,
  createPatentCollectionSetting,
  getPatentCollectionSettings,
  updatePatentCollectionSetting,
  deletePatentCollectionSetting,
  startPatentCollection,
  getPatentCollectionStatus,
} from '../../services/userService';
import { createUserContainer } from '../../services/userService';
import type { KnowledgeContainer } from './my-knowledge/components/KnowledgeContainerTree';

interface PatentSearchConfig {
  ipc_codes?: string[];
  keywords?: string[];
  applicants?: string[];
}

interface PatentCollectionSetting {
  setting_id: number;
  container_id: string;
  search_config: PatentSearchConfig;
  max_results: number;
  auto_download_pdf: boolean;
  auto_generate_embeddings: boolean;
  schedule_type: string;
  schedule_config?: Record<string, unknown> | null;
  is_active: boolean;
  last_collection_date?: string | null;
  last_collection_result?: {
    collected: number;
    errors: number;
  } | null;
}

interface TaskStatus {
  settingId: number;
  taskId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progressCurrent: number;
  progressTotal: number;
  collected: number;
  errors: number;
  message?: string;
  completedAt?: string;
}

const toArray = (value: string) =>
  value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);

const SummaryCard: React.FC<{ title: string; value: React.ReactNode; icon: React.ReactNode }> = ({ title, value, icon }) => (
  <div className="flex items-center gap-3 bg-white rounded-lg border border-gray-200 px-4 py-3 shadow-sm">
    <div className="p-2 rounded-full bg-blue-50 text-blue-600">{icon}</div>
    <div>
      <p className="text-sm text-gray-500">{title}</p>
      <p className="text-xl font-semibold text-gray-900">{value}</p>
    </div>
  </div>
);

const PatentCollectionSettings: React.FC = () => {
  const [containers, setContainers] = useState<KnowledgeContainer[]>([]);
  const [settings, setSettings] = useState<PatentCollectionSetting[]>([]);
  const [loading, setLoading] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [selectedContainer, setSelectedContainer] = useState('');
  const [ipcCodes, setIpcCodes] = useState('');
  const [keywords, setKeywords] = useState('');
  const [applicants, setApplicants] = useState('');
  const [maxResults, setMaxResults] = useState(100);
  const [activeTasks, setActiveTasks] = useState<Record<number, TaskStatus>>({});
  const [isCreatingContainer, setIsCreatingContainer] = useState(false);
  const [newContainerName, setNewContainerName] = useState('');
  const [newContainerDesc, setNewContainerDesc] = useState('');
  const [editingSettingId, setEditingSettingId] = useState<number | null>(null);

  const flattenContainers = (nodes: KnowledgeContainer[]): KnowledgeContainer[] => {
    const list: KnowledgeContainer[] = [];
    const walk = (items: KnowledgeContainer[]) => {
      items.forEach((c) => {
        list.push(c);
        if (c.children?.length) walk(c.children);
      });
    };
    walk(nodes);
    return list;
  };

  const formatContainerLabel = (c: KnowledgeContainer) => {
    if (c.path) {
      return `${c.name} (${c.path})`;
    }
    return c.name;
  };

  const lastCollection = useMemo(() => {
    const dates = settings
      .map((s) => (s.last_collection_date ? new Date(s.last_collection_date) : null))
      .filter((d): d is Date => !!d);
    if (!dates.length) return '-';
    const latest = dates.reduce((a, b) => (a > b ? a : b));
    return latest.toLocaleString('ko-KR');
  }, [settings]);

  const totalSettings = settings.length;
  const runningTasks = Object.values(activeTasks).filter((t) => t.status === 'running').length;

  const loadContainers = async () => {
    try {
      const data = await getMyContainers();
      const flat = flattenContainers(data || []);
      const editable = flat.filter((c) => c.permission !== 'NONE' && (c.can_upload || c.permission === 'OWNER' || c.permission === 'EDITOR'));
      setContainers(editable);
      if (!selectedContainer && editable.length) {
        setSelectedContainer(editable[0].id || '');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadSettings = async () => {
    try {
      const data = await getPatentCollectionSettings();
      setSettings(data || []);
    } catch (err) {
      console.error(err);
    }
  };

  const clearEditMode = (opts?: { keepContainer?: boolean }) => {
    const keepContainer = opts?.keepContainer ?? true;
    setEditingSettingId(null);
    setIpcCodes('');
    setKeywords('');
    setApplicants('');
    setMaxResults(100);
    if (!keepContainer) {
      setSelectedContainer('');
    }
  };

  const enterEditMode = (setting: PatentCollectionSetting) => {
    setEditingSettingId(setting.setting_id);
    setSelectedContainer(setting.container_id || '');
    const { ipc_codes, keywords, applicants } = setting.search_config || {};
    setIpcCodes((ipc_codes || []).join(', '));
    setKeywords((keywords || []).join(', '));
    setApplicants((applicants || []).join(', '));
    setMaxResults(setting.max_results ?? 100);
  };

  const handleCreateContainer = async () => {
    if (!newContainerName.trim()) {
      alert('컨테이너 이름을 입력하세요.');
      return;
    }
    setIsCreatingContainer(true);
    try {
      const res = await createUserContainer({
        container_name: newContainerName.trim(),
        description: newContainerDesc.trim() || undefined,
        parent_container_id: selectedContainer || undefined,
      });
      if (res?.success) {
        await loadContainers();
        setSelectedContainer(res.container_id || '');
        setNewContainerName('');
        setNewContainerDesc('');
        alert('✅ 컨테이너가 생성되었습니다.');
      } else {
        alert(res?.message || '❌ 컨테이너 생성에 실패했습니다.');
      }
    } catch (err: any) {
      console.error(err);
      alert(err?.response?.data?.detail || '❌ 컨테이너 생성 중 오류가 발생했습니다.');
    } finally {
      setIsCreatingContainer(false);
    }
  };

  const pollTask = async (settingId: number, taskId: string) => {
    try {
      const res = await getPatentCollectionStatus(taskId);
      const status = (res.status || 'running') as TaskStatus['status'];
      const collected = res.collected_count || 0;
      const total = res.progress_total || 0;
      const errors = res.error_count || 0;

      // 상태별 메시지 생성
      let message = '';
      if (status === 'completed') {
        if (collected === 0) {
          message = '⚠️ 검색 조건에 맞는 특허가 없습니다. 검색 조건을 조정해보세요.';
        } else {
          message = `✅ 수집 완료: ${collected}건 성공${errors > 0 ? `, ${errors}건 실패` : ''}`;
        }
      } else if (status === 'failed') {
        message = '❌ 수집 작업이 실패했습니다.';
      } else if (status === 'running') {
        message = `🔄 수집 중... (${res.progress_current || 0}/${total})`;
      }

      setActiveTasks((prev) => ({
        ...prev,
        [settingId]: {
          settingId,
          taskId,
          status,
          progressCurrent: res.progress_current || 0,
          progressTotal: total,
          collected,
          errors,
          message,
          completedAt: (status === 'completed' || status === 'failed') ? new Date().toISOString() : undefined,
        },
      }));

      // 완료 또는 실패 시 5초 후 상태 제거
      if (status === 'completed' || status === 'failed') {
        setTimeout(() => {
          setActiveTasks((prev) => {
            const copy = { ...prev };
            delete copy[settingId];
            return copy;
          });
        }, 5000);
        await loadSettings();
      }
    } catch (err) {
      console.error('status check failed', err);
    }
  };

  useEffect(() => {
    loadContainers();
    loadSettings();
  }, []);

  useEffect(() => {
    if (Object.keys(activeTasks).length === 0) return;
    const timer = setInterval(() => {
      Object.values(activeTasks).forEach((t) => pollTask(t.settingId, t.taskId));
    }, 3000);
    return () => clearInterval(timer);
  }, [activeTasks]);

  const handleSave = async () => {
    if (!selectedContainer) {
      alert('대상 컨테이너를 선택하세요.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        container_id: selectedContainer,
        search_config: {
          ipc_codes: toArray(ipcCodes),
          keywords: toArray(keywords),
          applicants: toArray(applicants),
        },
        max_results: maxResults,
        // 정책: PDF는 필요 시 뷰어에서 다운로드, 서지정보는 항상 색인/임베딩
        auto_download_pdf: false,
        auto_generate_embeddings: true,
        schedule_type: 'manual',
      };

      if (editingSettingId !== null) {
        await updatePatentCollectionSetting(editingSettingId, payload);
        await loadSettings();
        clearEditMode({ keepContainer: true });
        alert('✅ 수집 설정이 수정되었습니다.');
      } else {
        await createPatentCollectionSetting(payload);
        await loadSettings();
        alert('✅ 수집 설정이 저장되었습니다.');
      }
    } catch (err) {
      console.error(err);
      alert(editingSettingId !== null ? '❌ 설정 수정에 실패했습니다.' : '❌ 설정 저장에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (settingId: number) => {
    if (!window.confirm('이 수집 설정을 삭제할까요?')) return;
    try {
      await deletePatentCollectionSetting(settingId);
      setActiveTasks((prev) => {
        const copy = { ...prev };
        delete copy[settingId];
        return copy;
      });
      if (editingSettingId === settingId) {
        clearEditMode({ keepContainer: true });
      }
      await loadSettings();
      alert('✅ 수집 설정이 삭제되었습니다.');
    } catch (err) {
      console.error(err);
      alert('❌ 설정 삭제에 실패했습니다.');
    }
  };

  const handleStart = async (settingId: number) => {
    if (!window.confirm('특허 수집을 시작할까요?')) return;
    setIsStarting(true);
    try {
      const res = await startPatentCollection({ setting_id: settingId });
      const taskId = res.task_id;
      setActiveTasks((prev) => ({
        ...prev,
        [settingId]: {
          settingId,
          taskId,
          status: 'pending',
          progressCurrent: 0,
          progressTotal: 0,
          collected: 0,
          errors: 0,
          message: '🚀 수집 작업을 시작합니다...',
        },
      }));
      await pollTask(settingId, taskId);
    } catch (err) {
      console.error(err);
      setActiveTasks((prev) => ({
        ...prev,
        [settingId]: {
          ...prev[settingId],
          status: 'failed',
          message: '❌ 수집 시작에 실패했습니다.',
        },
      }));
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-full bg-blue-50 text-blue-600">
          <Database className="w-5 h-5" />
        </div>
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">특허 수집 설정</h2>
          <p className="text-sm text-gray-500">KIPRIS에서 특허를 검색해 지정 컨테이너에 저장합니다.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard title="마지막 수집" value={lastCollection} icon={<Clock className="w-5 h-5" />} />
        <SummaryCard title="설정 수" value={totalSettings} icon={<SettingsIcon className="w-5 h-5" />} />
        <SummaryCard title="진행 중" value={runningTasks} icon={<Play className="w-5 h-5" />} />
        <SummaryCard title="컨테이너" value={containers.length} icon={<Folder className="w-5 h-5" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 폼 */}
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5 space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <SettingsIcon className="w-5 h-5 text-blue-600" /> {editingSettingId !== null ? '수집 설정 수정' : '새 수집 설정'}
          </h3>

          <div className="space-y-3">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">대상 컨테이너</label>
              <div className="flex gap-2">
                <select
                  value={selectedContainer}
                  onChange={(e) => setSelectedContainer(e.target.value)}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">컨테이너 선택...</option>
                  {selectedContainer && !containers.some((c) => c.id === selectedContainer) && (
                    <option value={selectedContainer}>{selectedContainer}</option>
                  )}
                  {containers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {formatContainerLabel(c)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    setNewContainerName('');
                    setNewContainerDesc('');
                    const dialog = document.getElementById('container-create-dialog') as HTMLDialogElement | null;
                    dialog?.showModal();
                  }}
                  className="shrink-0 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  새로 만들기
                </button>
              </div>
            </div>

            <dialog id="container-create-dialog" className="rounded-lg p-0 shadow-xl">
              <div className="p-5 w-[360px] space-y-3">
                <h4 className="text-lg font-semibold text-gray-900">새 컨테이너 만들기</h4>
                <div className="space-y-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">컨테이너 이름</label>
                    <input
                      value={newContainerName}
                      onChange={(e) => setNewContainerName(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="예: 특허_임시_컨테이너"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">설명 (선택)</label>
                    <textarea
                      value={newContainerDesc}
                      onChange={(e) => setNewContainerDesc(e.target.value)}
                      className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                      rows={2}
                      placeholder="임시 수집용 컨테이너 설명"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => (document.getElementById('container-create-dialog') as HTMLDialogElement | null)?.close()}
                    className="px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    취소
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await handleCreateContainer();
                      (document.getElementById('container-create-dialog') as HTMLDialogElement | null)?.close();
                    }}
                    disabled={isCreatingContainer}
                    className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
                  >
                    {isCreatingContainer ? '생성 중...' : '생성'}
                  </button>
                </div>
              </div>
            </dialog>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">IPC/CPC 코드 (콤마 구분)</label>
              <input
                value={ipcCodes}
                onChange={(e) => setIpcCodes(e.target.value)}
                placeholder="예: G06N, G06F, H04L"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">예) G06N: 인공지능, G06F: 컴퓨터, H04L: 통신</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">키워드 (콤마 구분)</label>
              <input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="예: 인공지능, 딥러닝, 머신러닝"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">출원인 (콤마 구분)</label>
              <input
                value={applicants}
                onChange={(e) => setApplicants(e.target.value)}
                placeholder="예: 삼성전자, LG전자, SK하이닉스"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">최대 수집 건수</label>
              <input
                type="number"
                min={10}
                max={500}
                value={maxResults}
                onChange={(e) => setMaxResults(Number(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <button
              onClick={handleSave}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? '저장 중...' : editingSettingId !== null ? '수정 저장' : '수집 설정 저장'}
            </button>

            {editingSettingId !== null && (
              <button
                type="button"
                onClick={() => clearEditMode({ keepContainer: true })}
                className="w-full border border-gray-300 text-gray-700 py-2 rounded-lg font-semibold hover:bg-gray-50"
              >
                편집 취소
              </button>
            )}
          </div>
        </div>

        {/* 설정 목록 */}
        <div className="bg-white border border-gray-200 rounded-lg shadow-sm p-5 space-y-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-600" /> 저장된 설정
          </h3>

          {settings.length === 0 && (
            <div className="border border-dashed border-gray-300 rounded-lg p-6 text-center text-gray-500">
              아직 저장된 설정이 없습니다.
            </div>
          )}

          <div className="space-y-3">
            {settings.map((s) => {
              const tags: string[] = [];
              const { ipc_codes, keywords, applicants } = s.search_config || {};
              if (ipc_codes?.length) tags.push(`IPC ${ipc_codes.join(', ')}`);
              if (keywords?.length) tags.push(`키워드 ${keywords.join(', ')}`);
              if (applicants?.length) tags.push(`출원인 ${applicants.join(', ')}`);

              const task = activeTasks[s.setting_id];

              return (
                <div key={s.setting_id} className="border border-gray-200 rounded-lg p-4 hover:border-blue-200 transition">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-500">컨테이너</p>
                      <p className="text-base font-semibold text-gray-900">{s.container_id}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => enterEditMode(s)}
                        className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                      >
                        수정
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(s.setting_id)}
                        className="px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                      >
                        삭제
                      </button>
                      <button
                        onClick={() => handleStart(s.setting_id)}
                        disabled={isStarting}
                        className="flex items-center gap-2 bg-green-600 text-white px-3 py-2 rounded-lg text-sm font-semibold hover:bg-green-700 disabled:bg-gray-400"
                      >
                        <Play className="w-4 h-4" /> 수집 시작
                      </button>
                    </div>
                  </div>

                  <div className="mt-2 flex flex-wrap gap-2 text-sm text-gray-600">
                    {tags.length === 0 && <span className="text-gray-400">조건 없음</span>}
                    {tags.map((tag) => (
                      <span key={tag} className="inline-flex items-center gap-1 bg-blue-50 text-blue-700 px-2 py-1 rounded-full">
                        <Tag className="w-3 h-3" /> {tag}
                      </span>
                    ))}
                  </div>

                  <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-700">
                    <div className="flex items-center gap-2">
                      <SettingsIcon className="w-4 h-4 text-gray-400" />
                      <span>서지정보 수집 + 검색 색인/임베딩</span>
                    </div>
                  </div>

                  {task && (
                    <div className="mt-3 space-y-2">
                      {/* 상태 메시지 */}
                      <div className={`text-sm font-medium ${
                        task.status === 'completed' && task.collected > 0 ? 'text-green-700' :
                        task.status === 'completed' && task.collected === 0 ? 'text-yellow-700' :
                        task.status === 'failed' ? 'text-red-700' :
                        'text-blue-700'
                      }`}>
                        {task.message || '처리 중...'}
                      </div>

                      {/* 진행률 바 (실행 중일 때만) */}
                      {task.status === 'running' && task.progressTotal > 0 && (
                        <>
                          <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                            <span>진행률</span>
                            <span>
                              {task.progressCurrent}/{task.progressTotal} (성공 {task.collected}건{task.errors > 0 ? `, 실패 ${task.errors}건` : ''})
                            </span>
                          </div>
                          <div className="w-full bg-gray-100 rounded-full h-2">
                            <div
                              className="h-2 rounded-full bg-blue-600 transition-all duration-300"
                              style={{ width: `${Math.floor((task.progressCurrent / task.progressTotal) * 100)}%` }}
                            />
                          </div>
                        </>
                      )}

                      {/* 완료 시 결과 요약 */}
                      {task.status === 'completed' && (
                        <div className="bg-gray-50 rounded p-3 text-xs space-y-1">
                          <div className="flex justify-between">
                            <span className="text-gray-600">총 수집:</span>
                            <span className="font-semibold">{task.collected}건</span>
                          </div>
                          {task.errors > 0 && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">오류:</span>
                              <span className="font-semibold text-red-600">{task.errors}건</span>
                            </div>
                          )}
                          {task.completedAt && (
                            <div className="flex justify-between text-gray-500">
                              <span>완료 시간:</span>
                              <span>{new Date(task.completedAt).toLocaleTimeString('ko-KR')}</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* 마지막 수집 정보 */}
                  {!task && s.last_collection_date && (
                    <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200">
                      <div className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2 text-gray-600">
                          <Clock className="w-4 h-4" />
                          <span>마지막 수집</span>
                        </div>
                        <span className="font-medium text-gray-900">{new Date(s.last_collection_date).toLocaleString('ko-KR')}</span>
                      </div>
                      {s.last_collection_result && (
                        <div className="mt-2 flex items-center justify-between text-xs">
                          <span className="text-gray-600">결과</span>
                          <span className={`font-semibold ${
                            s.last_collection_result.collected > 0 ? 'text-green-600' : 'text-yellow-600'
                          }`}>
                            {s.last_collection_result.collected}건 수집
                            {s.last_collection_result.errors > 0 && `, ${s.last_collection_result.errors}건 실패`}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PatentCollectionSettings;
