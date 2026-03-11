import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "cut-corner-sm inline-flex w-fit shrink-0 items-center justify-center border px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] whitespace-nowrap transition-colors",
  {
    variants: {
      variant: {
        default: "border-[#040405] bg-[#040405] text-white",
        secondary: "border-[#d6d6d8] bg-[#ececef] text-[#040405]",
        outline: "border-[#3e3e40] bg-transparent text-current",
        success: "border-[#14c8a8]/35 bg-[#14c8a8]/12 text-[#0f8f78]",
        warning: "border-[#f4b942]/35 bg-[#f4b942]/14 text-[#8d5f00]",
        low: "border-[#ff5f7d]/35 bg-[#ff5f7d]/12 text-[#b21846]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge }
