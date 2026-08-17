type VehicleCountProps = {
  count: number;
};

export function VehicleCount({ count }: VehicleCountProps) {
  return <span className="text-2xl font-semibold text-zinc-900">{count}</span>;
}
