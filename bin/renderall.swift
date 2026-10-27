// PDF 逐页转 PNG（校验打印结果：分页、压线、是否有内容被裁）
// 编译：swiftc -O renderall.swift -o renderall
// 用法：./renderall <pdf> <outdir> [scale]   默认 scale=2
import Foundation
import PDFKit
import AppKit
import CoreGraphics

let args = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: args[1]))!
let outdir = args[2]
let scale: CGFloat = args.count > 3 ? CGFloat(Double(args[3])!) : 2.0
try? FileManager.default.createDirectory(atPath: outdir, withIntermediateDirectories: true)
for i in 0..<doc.pageCount {
    let page = doc.page(at: i)!
    let rect = page.bounds(for: .mediaBox)
    let w = Int(rect.width * scale), h = Int(rect.height * scale)
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpaceCreateDeviceRGB(),
                        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    let rep = NSBitmapImageRep(cgImage: ctx.makeImage()!)
    let data = rep.representation(using: .png, properties: [:])!
    let f = String(format: "%@/p%03d.png", outdir, i + 1)   // 三位零填充，与 ch11 页图命名一致
    try! data.write(to: URL(fileURLWithPath: f))
    print("saved", f, w, h)
}
