// 바텀시트 공통 컴포넌트
export default function BottomSheet({ open, onClose, title, children }) {
  if (!open) return null;

  return (
    <div className="absolute inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-t-3xl pt-3 pb-8 max-h-[70%] overflow-y-auto">
        <div className="flex justify-center mb-3">
          <div className="w-10 h-1 bg-gray-200 rounded-full" />
        </div>
        {title && (
          <div className="px-5 mb-4">
            <h3 className="text-[16px] font-semibold text-gray-900">{title}</h3>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}