import { useState } from 'react';
import { useI18n } from '../locales';
import { isDataScanFile, isInSkippedDataDir, scanDataDirHandle } from '../utils/fomodPlugins';

interface DataDirModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentDataPath: string | null;
  detectedPlugins: Set<string>;
  onApplyData: (path: string, plugins: Set<string>) => void;
}

export default function DataDirModal({
  isOpen,
  onClose,
  currentDataPath,
  detectedPlugins,
  onApplyData,
}: DataDirModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.dataDir;
  const c = strings.common;

  const [customInput, setCustomInput] = useState<string>(
    Array.from(detectedPlugins).join('\n')
  );
  const [pathName, setPathName] = useState<string>(
    currentDataPath || 'C:/Program Files (x86)/Steam/steamapps/common/Skyrim Special Edition/Data'
  );

  if (!isOpen) return null;

  const presetLoadOrders = [
    {
      name: m.presetBaseName,
      desc: m.presetBaseDesc,
      plugins: [
        'skyrim.esm',
        'update.esm',
        'dawnguard.esm',
        'hearthfires.esm',
        'dragonborn.esm',
      ],
    },
    {
      name: m.presetEssentialName,
      desc: m.presetEssentialDesc,
      plugins: [
        'skyrim.esm',
        'update.esm',
        'dawnguard.esm',
        'hearthfires.esm',
        'dragonborn.esm',
        'unofficial skyrim special edition patch.esp',
        'skyui_se.esp',
        'skee64.dll',
        'skse64_2_02_06.dll',
      ],
    },
    {
      name: m.presetPhysicsName,
      desc: m.presetPhysicsDesc,
      plugins: [
        'skyrim.esm',
        'update.esm',
        'dawnguard.esm',
        'hearthfires.esm',
        'dragonborn.esm',
        'skyui_se.esp',
        'cbpc.dll',
        'hdtsmp64.dll',
        'skee64.dll',
      ],
    },
  ];

  const handleSelectLocalFolder = async () => {
    try {
      if ('showDirectoryPicker' in window) {
        // Chromium File System Access API
        const dirHandle = await (window as unknown as { showDirectoryPicker: () => Promise<FileSystemDirectoryHandle> }).showDirectoryPicker();
        const found = await scanDataDirHandle(dirHandle);
        const p = dirHandle.name ? `${dirHandle.name}` : 'Data';
        onApplyData(p, found);
        onClose();
      } else {
        // Fallback file input
        const input = document.createElement('input');
        input.type = 'file';
        (input as HTMLInputElement & { webkitdirectory?: boolean }).webkitdirectory = true;
        input.onchange = (e) => {
          const files = (e.target as HTMLInputElement).files;
          if (!files || files.length === 0) return;
          const found = new Set<string>();
          for (let i = 0; i < files.length; i++) {
            const rel = (files[i] as File & { webkitRelativePath?: string }).webkitRelativePath || files[i].name;
            if (isDataScanFile(files[i].name) && !isInSkippedDataDir(rel)) found.add(files[i].name.toLowerCase());
          }
          onApplyData('Data', found);
          onClose();
        };
        input.click();
      }
    } catch {
      // User cancelled
    }
  };

  const applyPreset = (preset: typeof presetLoadOrders[0]) => {
    const set = new Set<string>(preset.plugins.map(p => p.toLowerCase()));
    onApplyData(`Preset: ${preset.name}`, set);
    onClose();
  };

  const applyManual = () => {
    const list = customInput
      .split('\n')
      .map(s => s.trim().toLowerCase())
      .filter(Boolean);
    onApplyData(pathName.trim() || 'Data', new Set(list));
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded p-6 flex flex-col max-h-[90vh]"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between pb-3 border-b border-[#333333]">
          <h2 className="text-base font-bold text-white tracking-wide">
            📂 {m.title}
          </h2>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        <div className="py-4 space-y-4 overflow-y-auto">
          <div>
            <p className="text-xs text-[#aaa] mb-2 leading-relaxed">
              {m.desc}
            </p>

            <button
              onClick={handleSelectLocalFolder}
              className="w-full py-2.5 px-4 bg-[#333333] hover:bg-[#444444] text-white font-medium text-sm rounded transition-colors flex items-center justify-center gap-2 cursor-pointer border border-[#444444]"
            >
              <span>{m.browseFolder}</span>
            </button>
          </div>

          <div className="border-t border-[#2d2d2d] pt-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#888] mb-2">
              {m.loadPresets}
            </h3>
            <div className="space-y-2">
              {presetLoadOrders.map(preset => (
                <div
                  key={preset.name}
                  onClick={() => applyPreset(preset)}
                  className="p-3 bg-[#222222] hover:bg-[#282828] border border-[#333333] hover:border-[#0ea5e9] rounded cursor-pointer transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold text-white">{preset.name}</span>
                    <span className="text-xs text-[#0ea5e9] font-medium">{c.apply}</span>
                  </div>
                  <p className="text-xs text-[#999] mt-0.5">{preset.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-[#2d2d2d] pt-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#888] mb-1">
              {m.manualInput}
            </h3>
            <label className="text-xs text-[#aaa] block mb-1">
              {m.currentPath}
            </label>
            <input
              type="text"
              value={pathName}
              onChange={e => setPathName(e.target.value)}
              className="w-full text-xs bg-[#222222] border border-[#333333] rounded px-2.5 py-1.5 text-[#ddd] mb-2 focus:outline-hidden focus:border-[#0ea5e9]"
            />

            <label className="text-xs text-[#aaa] block mb-1">
              {m.detectedPlugins} (1 / ligne) :
            </label>
            <textarea
              rows={5}
              value={customInput}
              onChange={e => setCustomInput(e.target.value)}
              placeholder="ex: skyui_se.esp&#10;cbpc.dll"
              className="w-full text-xs font-mono bg-[#222222] border border-[#333333] rounded p-2 text-[#ddd] focus:outline-hidden focus:border-[#0ea5e9]"
            />
          </div>
        </div>

        <div className="pt-3 border-t border-[#333333] flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-[#333333] hover:bg-[#444444] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.cancel}
          </button>
          <button
            onClick={applyManual}
            className="px-5 py-2 bg-[#0ea5e9] hover:bg-[#0284c7] text-white text-xs font-medium rounded transition-colors cursor-pointer"
          >
            {c.apply}
          </button>
        </div>
      </div>
    </div>
  );
}
