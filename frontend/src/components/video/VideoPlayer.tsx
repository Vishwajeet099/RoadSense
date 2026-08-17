type VideoPlayerProps = {
  src: string;
};

export function VideoPlayer({ src }: VideoPlayerProps) {
  return <video className="aspect-video w-full rounded-md bg-black" controls src={src} />;
}
