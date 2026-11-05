import { useI18n } from '../locales';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

/** « À propos de fOMODSIM » (Socle, modèle swift/AboutWindow.swift) : colonne de 300 px centrée, marges de 28 px. */
export default function AboutModal({ isOpen, onClose }: AboutModalProps) {
  const { strings } = useI18n();
  const a = strings.about;
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-label={a.title}
        className="bg-[#1e1e1e] shadow-2xl rounded p-7 flex flex-col items-center text-center text-xs text-[#f5f5f5]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="w-[300px] flex flex-col items-center gap-3">
          <img src="/logo.svg" alt="" className="w-[84px] h-[84px]" />
          <div className="flex flex-col items-center gap-1.5">
            <h2 className="text-[17px] font-bold text-white">
              <span className="text-[#1677dc]">f</span>OMODSIM
            </h2>
            <p className="text-[#a3a3a3]">{a.version.replace('{v}', __APP_VERSION__)}</p>
          </div>
          <p className="mt-1.5 leading-relaxed">{a.tagline}</p>
          <p className="font-bold">Starbudweiser &amp; Claude Code (Anthropic)</p>
          <p>{a.license}</p>
          <p className="text-[#a3a3a3]">{a.disclaimer}</p>
          <p className="text-[#a3a3a3] leading-relaxed">{a.credit}</p>
          <button
            autoFocus
            onClick={onClose}
            className="mt-2 py-2 px-4 bg-[#333333] hover:bg-[#404040] text-white text-xs font-bold rounded transition-colors cursor-pointer"
          >
            {a.close}
          </button>
        </div>
      </div>
    </div>
  );
}
