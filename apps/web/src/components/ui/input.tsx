import * as React from "react"

import { cn } from "@/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "cut-corner-sm file:text-foreground placeholder:text-[#7f7f82] selection:bg-[#ff0074] selection:text-white flex h-14 w-full min-w-0 border border-[#2a2a2b] bg-[#111214] px-5 py-3 text-sm text-[#f2f2f3] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.02)] transition-[color,box-shadow,border-color] outline-none file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 focus-visible:border-[#ff0074] focus-visible:ring-2 focus-visible:ring-[#ff0074]/25",
        className,
      )}
      {...props}
    />
  )
}

export { Input }
