import React, { useEffect, useMemo, useState } from 'react';
import { Database, Folder, Play, Settings as SettingsIcon, Download, Clock, Tag } from 'lucide-react';
import {
  getMyContainers,
  createPatentCollectionSetting,
  getPatentCollectionSettings,
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
}

interface TaskStatus {
  settingId: number;
  taskId: string;
  status: string;
  progressCurrent: number;
  progressTotal: number;
  collected: number;
  errors: number;
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
  const [autoDownloadPdf, setAutoDownloadPdf] = useState(false);
  const [autoGenerateEmbeddings, setAutoGenerateEmbeddings] = useState(true);
  const [activeTasks, setActiveTasks] = useState<Record<number, TaskStatus>>({});
  const [isCreatingContainer, setIsCreatingContainer] = useState(false);
  const [newContainerName, setNewContainerName] = useState('');
  const [newContainerDesc, setNewContainerDesc] = useState('');

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
      setActiveTasks((prev) => ({
        ...prev,
        [settingId]: {
          settingId,
          taskId,
          status: res.status,
          progressCurrent: res.progress_current,
          progressTotal: res.progress_total,
          collected: res.collected_count,
          errors: res.error_count,
        },
      }));
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
      await createPatentCollectionSetting({
        container_id: selectedContainer,
        search_config: {
          ipc_codes: toArray(ipcCodes),
          keywords: toArray(keywords),
          applicants: toArray(applicants),
        },
        max_results: maxResults,
        auto_download_pdf: autoDownloadPdf,
        auto_generate_embeddings: autoGenerateEmbeddings,
        schedule_type: 'manual',
      });
      await loadSettings();
      alert('✅ 수집 설정이 저장되었습니다.');
    } catch (err) {
      console.error(err);
      alert('❌ 설정 저장에 실패했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleStart = async (settingId: number) => {
    if (!confirm('특허 수집을 시작할까요?')) return;
    setIsStarting(true);
    try {
      const res = await startPatentCollection({ setting_id: settingId });
      const taskId = res.task_id;
      setActiveTasks((prev) => ({
        ...prev,
        [settingId]: {
          settingId,
          taskId,
          status: 'running',
          progressCurrent: 0,
          progressTotal: 0,
          collected: 0,
          errors: 0,
        },
      }));
      await pollTask(settingId, taskId);
      alert(`✅ 수집을 시작했습니다. Task: ${taskId}`);
    } catch (err) {
      console.error(err);
      alert('❌ 수집 시작에 실패했습니다.');
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
            <SettingsIcon className="w-5 h-5 text-blue-600" /> 새 수집 설정
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

            <div className="flex items-center gap-3 text-sm">
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={autoDownloadPdf}
                  onChange={(e) => setAutoDownloadPdf(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-gray-700">PDF 자동 다운로드</span>
              </label>
              <label className="inline-flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={autoGenerateEmbeddings}
                  onChange={(e) => setAutoGenerateEmbeddings(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-gray-700">임베딩 생성</span>
              </label>
            </div>

            <button
              onClick={handleSave}
              disabled={loading}
              className="w-full bg-blue-600 text-white py-2 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400"
            >
              {loading ? '저장 중...' : '수집 설정 저장'}
            </button>
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
                    <button
                      onClick={() => handleStart(s.setting_id)}
                      disabled={isStarting}
                      className="flex items-center gap-2 bg-green-600 text-white px-3 py-2 rounded-lg text-sm font-semibold hover:bg-green-700 disabled:bg-gray-400"
                    >
                      <Play className="w-4 h-4" /> 수집 시작
                    </button>
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
                      <Download className="w-4 h-4 text-gray-400" />
                      <span>PDF {s.auto_download_pdf ? '자동' : '수동'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <SettingsIcon className="w-4 h-4 text-gray-400" />
                      <span>임베딩 {s.auto_generate_embeddings ? '생성' : '생성 안 함'}</span>
                    </div>
                  </div>

                  {task && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs text-gray-600 mb-1">
                        <span>진행률</span>
                        <span>
                          {task.progressCurrent}/{task.progressTotal} (성공 {task.collected}, 오류 {task.errors})
                        </span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full bg-blue-600"
                          style={{ width: task.progressTotal ? `${Math.floor((task.progressCurrent / task.progressTotal) * 100)}%` : '0%' }}
                        />
                      </div>
                    </div>
                  )}

                  {s.last_collection_date && (
                    <p className="mt-2 text-xs text-gray-500">마지막 수집: {new Date(s.last_collection_date).toLocaleString('ko-KR')}</p>
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
