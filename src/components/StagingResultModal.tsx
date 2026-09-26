import { useState } from 'react';
import { StagingResult } from '../types/fomod';
import { exportStagingAsZip, writeStagingToLocalDirectoryHandle } from '../utils/fomodStaging';
import { useI18n } from '../locales';

interface StagingResultModalProps {
  isOpen: boolean;
  onClose: () => void;
  result: StagingResult | null;
  stagingPathDisplay: string;
  directWriteSuccess?: boolean;
}

export default function StagingResultModal({
  isOpen,
  onClose,
  result,
  stagingPathDisplay,
  directWriteSuccess = false,
}: StagingResultModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.staging;
  const c = strings.common;

  const [activeTab, setActiveTab] = useState<'files' | 'log'>('files');
  const [isExporting, setIsExporting] = useState(false);
  const [copiedNotification, setCopiedNotification] = useState(false);
  const [writeNotification, setWriteNotification] = useState<string | null>(null);

  if (!isOpen || !result) return null;

  const handleDownloadZip = async () => {
    try {
      setIsExporting(true);
      const zipBlob = await exportStagingAsZip(result);
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${result.stagingDirName || 'Staging'}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(m.zipError + err);
    } finally {
      setIsExporting(false);
    }
  };

  const handleWriteToLocalFolder = async () => {
    if (!('showDirectoryPicker' in window)) {
      alert(m.browserNotSupported);
      return;
    }

    try {
      setIsExporting(true);
      // @ts-expect-error File System Access API
      const rootHandle: FileSystemDirectoryHandle = await window.showDirectoryPicker({
        mode: 'readwrite',
      });
      const writeRes = await writeStagingToLocalDirectoryHandle(rootHandle, result);
      setWriteNotification(
        `✓ ${writeRes.writtenCount} ${m.writeSuccess} ("${writeRes.destinationFolderName}")`
      );
      setTimeout(() => setWriteNotification(null), 4000);
    } catch (e: unknown) {
      if ((e as { name?: string }).name !== 'AbortError') {
        alert(m.zipError + e);
      }
    } finally {
      setIsExporting(false);
    }
  };

  const handleCopyLog = () => {
    navigator.clipboard.writeText(result.log.join('\n'));
    setCopiedNotification(true);
    setTimeout(() => setCopiedNotification(false), 2000);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} Mo`;
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded p-6 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-3 border-b border-[#333333]">
          <div>
            <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
              <span className="text-[#0ea5e9]">✓</span> {m.title}
            </h2>
            <p className="text-xs text-[#aaa] mt-0.5 font-mono">
              {c.destination} {stagingPathDisplay}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        {directWriteSuccess && (
          <div className="mt-3 p-2.5 bg-[#14532d]/40 border border-[#22c55e] rounded text-xs text-[#86efac] flex items-center gap-2">
            <span>✓</span> {m.writeSuccess}
          </div>
        )}

        {writeNotification && (
          <div className="mt-3 p-2.5 bg-[#0369a1]/40 border border-[#38bdf8] rounded text-xs text-[#bae6fd] flex items-center gap-2">
            <span>✓</span> {writeNotification}
          </div>
        )}

        {/* Stats bar */}
        <div className="grid grid-cols-3 gap-3 my-4">
          <div className="bg-[#222222] border border-[#2e2e2e] p-3 rounded text-center">
            <div className="text-xl font-bold text-[#4ade80]">{result.totalCopied}</div>
            <div className="text-xs text-[#aaa] mt-0.5">{m.totalFiles} ({result.totalCopied})</div>
          </div>
          <div className="bg-[#222222] border border-[#2e2e2e] p-3 rounded text-center">
            <div
              className={`text-xl font-bold ${
                result.totalMissing > 0 ? 'text-[#f87171]' : 'text-[#888]'
              }`}
            >
              {result.totalMissing}
            </div>
            <div className="text-xs text-[#aaa] mt-0.5">Missing ({result.totalMissing})</div>
          </div>
          <div className="bg-[#222222] border border-[#2e2e2e] p-3 rounded text-center">
            <div className="text-xl font-bold text-[#38bdf8]">{formatSize(result.totalSize)}</div>
            <div className="text-xs text-[#aaa] mt-0.5">{m.totalSize}</div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={handleDownloadZip}
            disabled={isExporting}
            className="flex-1 min-w-[200px] py-2.5 px-4 bg-[#0ea5e9] hover:bg-[#0284c7] text-white font-medium text-xs rounded transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <span>📦 {m.downloadZip}</span>
          </button>

          <button
            onClick={handleWriteToLocalFolder}
            disabled={isExporting}
            className="flex-1 min-w-[200px] py-2.5 px-4 bg-[#333333] hover:bg-[#444444] text-white font-medium text-xs rounded transition-colors flex items-center justify-center gap-2 cursor-pointer border border-[#444444] disabled:opacity-50"
          >
            <span>📁 {m.writeLocal}</span>
          </button>

          <button
            onClick={handleCopyLog}
            className="py-2.5 px-3 bg-[#262626] hover:bg-[#333333] text-[#ddd] text-xs font-medium rounded transition-colors cursor-pointer border border-[#333333]"
            title="Copier le journal"
          >
            {copiedNotification ? '✓ Copié !' : '📋 Log'}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[#333333] mb-2 text-xs font-medium">
          <button
            onClick={() => setActiveTab('files')}
            className={`pb-2 px-3 border-b-2 transition-colors cursor-pointer ${
              activeTab === 'files'
                ? 'border-[#0ea5e9] text-white font-bold'
                : 'border-transparent text-[#888] hover:text-[#bbb]'
            }`}
          >
            {m.filesInstalled} ({result.items.length})
          </button>
          <button
            onClick={() => setActiveTab('log')}
            className={`pb-2 px-3 border-b-2 transition-colors cursor-pointer ${
              activeTab === 'log'
                ? 'border-[#0ea5e9] text-white font-bold'
                : 'border-transparent text-[#888] hover:text-[#bbb]'
            }`}
          >
            {m.stagingLog}
          </button>
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto bg-[#181818] border border-[#2a2a2a] rounded p-3 text-xs font-mono">
          {activeTab === 'files' ? (
            <div className="space-y-1.5">
              {result.items.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between py-1 px-2 hover:bg-[#222222] rounded text-[#ccc]"
                >
                  <span className="text-[#38bdf8] truncate mr-2" title={item.destinationPath}>
                    {item.destinationPath}
                  </span>
                  <div className="flex items-center gap-3 shrink-0 text-[#777] text-[11px]">
                    <span className="truncate max-w-[150px]" title={item.matchedFromOption}>
                      {item.matchedFromOption}
                    </span>
                    <span>{formatSize(item.size)}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-0.5 whitespace-pre-wrap">
              {result.log.map((line, idx) => {
                let color = 'text-[#aaa]';
                if (line.includes('[+ fichier]') || line.includes('[+ file]')) color = 'text-[#4ade80]';
                else if (line.includes('[+ dossier]') || line.includes('[+ folder]')) color = 'text-[#fbbf24]';
                else if (line.includes('[manquant]') || line.includes('[missing]')) color = 'text-[#f87171]';
                else if (line.startsWith('[') && line.endsWith(']'))
                  color = 'text-[#38bdf8] font-bold';

                return (
                  <div key={idx} className={color}>
                    {line}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-[#333333] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 bg-[#333333] hover:bg-[#444444] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.close}
          </button>
        </div>
      </div>
    </div>
  );
}
