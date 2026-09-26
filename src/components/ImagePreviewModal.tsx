import { useI18n } from '../locales';

interface ImagePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  imageUrl: string | null;
  title?: string;
}

export default function ImagePreviewModal({
  isOpen,
  onClose,
  imageUrl,
  title,
}: ImagePreviewModalProps) {
  const { strings } = useI18n();
  const m = strings.modals.imagePreview;
  const c = strings.common;

  if (!isOpen || !imageUrl) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4"
      onClick={onClose}
    >
      <div
        className="max-w-[95vw] max-h-[92vh] bg-[#1e1e1e] border border-[#333333] shadow-2xl rounded flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-4 py-2.5 bg-[#222222] border-b border-[#333333]">
          <span className="text-sm font-bold text-white tracking-wide truncate">
            {title ? `${m.title} — ${title}` : m.title}
          </span>
          <button
            onClick={onClose}
            className="text-[#999] hover:text-white text-xl leading-none px-2 cursor-pointer transition-colors"
            title={c.close}
          >
            &times;
          </button>
        </div>

        <div className="overflow-auto max-h-[84vh] p-2 flex items-center justify-center bg-[#181818]">
          <img
            src={imageUrl}
            alt={m.title}
            className="max-w-none object-contain rounded select-none cursor-default"
          />
        </div>
      </div>
    </div>
  );
}
