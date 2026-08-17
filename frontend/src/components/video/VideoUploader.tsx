"use client";

type VideoUploaderProps = {
  onSelect: (file: File) => void;
};

export function VideoUploader({ onSelect }: VideoUploaderProps) {
  return (
    <input
      accept="video/*"
      className="block w-full text-sm text-zinc-600 file:mr-4 file:rounded-md file:border-0 file:bg-signal file:px-4 file:py-2 file:text-sm file:font-medium file:text-white"
      type="file"
      onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) {
          onSelect(file);
        }
      }}
    />
  );
}
