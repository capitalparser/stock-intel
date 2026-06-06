import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { Candidate } from "../data/snapshot";
import { Badge } from "./Badges";
import { Sparkline } from "./Sparkline";

type CandidateTableProps = {
  candidates: Candidate[];
};

function formatNumber(value?: number | null) {
  return value == null ? "-" : value.toFixed(1);
}

function isBlocked(candidate: Candidate) {
  return candidate.status.toUpperCase().includes("BLOCK") || candidate.independence_status.toUpperCase().includes("BLOCK");
}

export function CandidateTable({ candidates }: CandidateTableProps) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "score", desc: true }]);
  const [globalFilter, setGlobalFilter] = useState("");

  const columns = useMemo<ColumnDef<Candidate>[]>(
    () => [
      {
        accessorKey: "ticker",
        header: "종목",
        cell: ({ row }) => (
          <div>
            <p className="font-semibold">{row.original.ticker}</p>
            <p className="text-xs text-textMuted">{row.original.company}</p>
          </div>
        ),
      },
      {
        accessorKey: "score",
        header: "매력도",
        cell: ({ row }) => formatNumber(row.original.score),
      },
      {
        accessorKey: "pe",
        header: "PER",
        cell: ({ row }) => formatNumber(row.original.pe),
      },
      {
        accessorKey: "strongest_lens",
        header: "렌즈",
        cell: ({ row }) => row.original.strongest_lens || row.original.linked_lenses[0]?.name || "-",
      },
      {
        id: "blocked",
        header: "상태",
        cell: ({ row }) =>
          isBlocked(row.original) ? <Badge tone="risk">BLOCKED</Badge> : <span className="text-xs text-textMuted">BLOCKED 확인</span>,
      },
      {
        id: "sparkline",
        header: "흐름",
        cell: ({ row }) => <Sparkline label={`${row.original.ticker} 가격 흐름`} values={row.original.price_series} />,
      },
    ],
    [],
  );

  const table = useReactTable({
    data: candidates,
    columns,
    state: { sorting, globalFilter },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  return (
    <section className="grid gap-md">
      <label className="text-sm font-semibold text-text">
        후보 필터
        <input
          className="mt-xs w-full rounded-sm border border-line bg-surface px-sm py-sm text-sm"
          value={globalFilter}
          onChange={(event) => setGlobalFilter(event.target.value)}
          placeholder="종목, 회사, 렌즈"
        />
      </label>
      <div className="overflow-x-auto rounded-md border border-line">
        <table className="w-full min-w-[760px] border-collapse text-sm">
          <thead className="bg-surfaceAlt text-left">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border-b border-line px-sm py-sm">
                    <button type="button" onClick={header.column.getToggleSortingHandler()} className="font-semibold">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </button>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className={isBlocked(row.original) ? "bg-red-50" : ""}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="border-b border-line px-sm py-sm align-top">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
