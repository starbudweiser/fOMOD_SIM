import { useI18n } from '../locales';

interface OpenModModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectArchive: () => void;
  onSelectFolder: () => void;
  onLoadSample: (sampleId: 'cbbe' | 'smim') => void;
}

export default function OpenModModal({
  isOpen,
  onClose,
  onSelectArchive,
  onSelectFolder,
  onLoadSample,
}: OpenModModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.openMod;
  const c = strings.common;

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded p-6 flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-3 border-b border-[#333333]">
          <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
            <span>📦</span> {m.title}
          </h2>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        <div className="py-4 space-y-4">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#888] mb-2">
              {m.fromComputer}
            </h3>
            <div className="space-y-2">
              <button
                onClick={() => {
                  onClose();
                  onSelectArchive();
                }}
                className="w-full p-3 bg-[#262626] hover:bg-[#303030] border border-[#383838] hover:border-[#fbbf24] rounded text-left transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-[#fbbf24] group-hover:text-[#f59e0b]">
                    {m.browseArchive}
                  </span>
                  <span className="text-xs text-[#4ade80] bg-[#4ade80]/10 px-1.5 py-0.5 rounded border border-[#4ade80]/30 font-medium">
                    {m.fullSupport}
                  </span>
                </div>
                <p className="text-xs text-[#aaa] mt-1 leading-relaxed">
                  {m.browseArchiveDesc}
                </p>
              </button>

              <button
                onClick={() => {
                  onClose();
                  onSelectFolder();
                }}
                className="w-full p-3 bg-[#262626] hover:bg-[#303030] border border-[#383838] hover:border-[#0ea5e9] rounded text-left transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-[#38bdf8] group-hover:text-[#0ea5e9]">
                    {m.browseFolder}
                  </span>
                  <span className="text-xs text-[#888]">{m.localFolder}</span>
                </div>
                <p className="text-xs text-[#aaa] mt-1 leading-relaxed">
                  {m.browseFolderDesc}
                </p>
              </button>
            </div>
          </div>

          <div className="border-t border-[#2d2d2d] pt-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#888] mb-2">
              {m.demoMods}
            </h3>
            <div className="space-y-2">
              <button
                onClick={() => {
                  onClose();
                  onLoadSample('cbbe');
                }}
                className="w-full p-3 bg-[#222222] hover:bg-[#282828] border border-[#333333] hover:border-[#4ade80] rounded text-left transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white">
                    CBBE - Caliente's Beautiful Bodies Enhancer SE
                  </span>
                  <span className="text-xs text-[#4ade80] font-semibold">{m.load}</span>
                </div>
                <p className="text-xs text-[#999] mt-0.5">
                  {m.cbbeDesc}
                </p>
              </button>

              <button
                onClick={() => {
                  onClose();
                  onLoadSample('smim');
                }}
                className="w-full p-3 bg-[#222222] hover:bg-[#282828] border border-[#333333] hover:border-[#4ade80] rounded text-left transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white">
                    SMIM - Static Mesh Improvement Mod
                  </span>
                  <span className="text-xs text-[#4ade80] font-semibold">{m.load}</span>
                </div>
                <p className="text-xs text-[#999] mt-0.5">
                  {m.smimDesc}
                </p>
              </button>
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-[#333333] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#333333] hover:bg-[#444444] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.close}
          </button>
        </div>
      </div>
    </div>
  );
}
