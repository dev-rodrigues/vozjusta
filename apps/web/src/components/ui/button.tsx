import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "cut-corner-sm inline-flex items-center justify-center gap-2 whitespace-nowrap border text-[11px] font-semibold uppercase tracking-[0.18em] transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
  {
    variants: {
      variant: {
        default:
          "border-[#ff0074] bg-[#ff0074] text-white shadow-[0_0_0_1px_rgba(255,0,116,0.35),0_18px_48px_rgba(255,0,116,0.16)] hover:-translate-y-0.5 hover:bg-[#ff1a81] active:translate-y-0",
        secondary:
          "border-[#d8d8da] bg-[#f2f2f3] text-[#040405] hover:-translate-y-0.5 hover:bg-white active:translate-y-0",
        outline:
          "border-[#3e3e40] bg-transparent text-current hover:-translate-y-0.5 hover:bg-white/5 active:translate-y-0",
        ghost: "border-transparent bg-transparent text-current hover:-translate-y-0.5 hover:bg-white/6 active:translate-y-0",
        destructive:
          "border-[#ff5f7d] bg-[#ff5f7d] text-white shadow-[0_18px_48px_rgba(255,95,125,0.18)] hover:-translate-y-0.5 hover:bg-[#ff6d89] active:translate-y-0",
      },
      size: {
        default: "h-12 px-5 py-2",
        sm: "h-10 px-4",
        lg: "h-14 px-8 text-xs",
        icon: "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
)

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button }
