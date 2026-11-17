import { useEffect, useRef, useState } from "react";
import { webglAvailable } from "../components/JourneyGlobe";

type Factory = (canvas: HTMLCanvasElement, opts: { reducedMotion: boolean }) => { dispose(): void };

interface Props {
  load: () => Promise<Factory>;
  className?: string;
  label: string;
}

/** Mounts a lazily loaded three.js scene; renders a static decorative backdrop without WebGL. */
export function ThreeCanvas({ load, className = "", label }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const [supported] = useState(webglAvailable);

  useEffect(() => {
    if (!supported || !ref.current) return;
    let handle: { dispose(): void } | null = null;
    let cancelled = false;
    const canvas = ref.current;
    const reducedMotion =
      typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    load().then((factory) => {
      if (!cancelled) handle = factory(canvas, { reducedMotion });
    });
    return () => {
      cancelled = true;
      handle?.dispose();
    };
  }, [supported, load]);

  if (!supported) return <div className={`${className} three-fallback`} role="img" aria-label={label} />;
  return <canvas ref={ref} className={className} role="img" aria-label={label} />;
}
