// render_pdf_pages — 按页范围把 PDF 渲成 PNG（PDFKit）。
// 用途：教材/手册三四百页，只想看 3~5 页（查一条曲线、核一个例题）时别整册渲。
// 编译：swiftc -O render_pdf_pages.swift -o render_pdf_pages
// 用法：./render_pdf_pages <pdf> <outdir> <first> <last> [scale=2]
//       页码从 1 起（PDF 内页序，不是书页号）；输出 p001.png … 按页数从 1 编号。
// 实测：406 页教材渲 352~360 页、scale 2 → 2382×1683，与 mdkit.py page 的整页渲结果一致。
// 整本/整章批量渲仍用 mdkit.py page 或 bin/renderall，别用这个逐段拼。

import Foundation
import PDFKit
import AppKit

let args = CommandLine.arguments
guard args.count >= 5,
      let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    print("usage: render_pdf_pages <pdf> <outdir> <first> <last> [scale]")
    exit(2)
}

let outDir = args[2]
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let first = max(1, Int(args[3]) ?? 1)
let last = min(doc.pageCount, Int(args[4]) ?? first)
let scale = args.count > 5 ? (Double(args[5]) ?? 2.0) : 2.0

var n = 0
for i in first...last {
    guard let page = doc.page(at: i - 1) else { continue }
    let box = page.bounds(for: .mediaBox)
    let w = Int((box.width * scale).rounded())
    let h = Int((box.height * scale).rounded())

    let image = NSImage(size: NSSize(width: w, height: h))
    image.lockFocus()
    NSColor.white.setFill()
    NSRect(x: 0, y: 0, width: w, height: h).fill()
    if let ctx = NSGraphicsContext.current?.cgContext {
        ctx.scaleBy(x: scale, y: scale)
        ctx.translateBy(x: -box.origin.x, y: -box.origin.y)
        page.draw(with: .mediaBox, to: ctx)
    }
    image.unlockFocus()

    guard let tiff = image.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:]) else {
        print("skip page \(i): render failed")
        continue
    }
    n += 1
    let out = String(format: "%@/p%03d.png", outDir, n)
    try? png.write(to: URL(fileURLWithPath: out))
    print("saved \(out) \(w) \(h)")
}
