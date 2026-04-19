type Props = {
  values: number[];
  height?: number;
  color?: string;
  fill?: string;
  max?: number;
  formatValue?: (n: number) => string;
};

export default function Sparkline({
  values,
  height = 48,
  color = "#0f172a",
  fill = "rgba(15, 23, 42, 0.1)",
  max,
  formatValue,
}: Props) {
  if (!values.length) {
    return (
      <div
        className="text-xs text-slate-400 flex items-center justify-center"
        style={{ height }}
      >
        collecting…
      </div>
    );
  }
  const vmax = max ?? Math.max(1, ...values);
  const W = 200;
  const H = height;
  const step = values.length > 1 ? W / (values.length - 1) : W;
  const points = values.map((v, i) => {
    const x = i * step;
    const y = H - (v / vmax) * H;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const line = "M" + points.join(" L");
  const area = line + ` L${(values.length - 1) * step},${H} L0,${H} Z`;
  const last = values[values.length - 1];

  return (
    <div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height }}
      >
        <path d={area} fill={fill} />
        <path d={line} fill="none" stroke={color} strokeWidth={1.5} />
      </svg>
      {formatValue && (
        <div className="text-xs text-slate-500 mt-1">now: {formatValue(last)}</div>
      )}
    </div>
  );
}
