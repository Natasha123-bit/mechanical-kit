// 只渲指定几页（bin/renderall 渲整本 406 页，校样两三页太贵）
// 编译：swiftc -O renderpages.swift -o renderpages
// 用法：./renderpages <pdf> <outdir> <scale> <p1,p2,...>   （1 起）
// 输出：<outdir>/p%03d.png
// 注意：多次调用要用不同 outdir，否则 p001.png 互相覆盖。
import Foundation
import PDFKit
import AppKit
import CoreGraphics

let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let outdir = a[2]
let scale: CGFloat = CGFloat(Double(a[3])!)
try? FileManager.default.createDirectory(atPath: outdir, withIntermediateDirectories: true)
for s in a[4].split(separator: ",") {
    let n = Int(s)!
    guard n >= 1, n <= doc.pageCount else { print("skip", n); continue }
    let page = doc.page(at: n - 1)!
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
    let f = String(format: "%@/p%03d.png", outdir, n)
    try! data.write(to: URL(fileURLWithPath: f))
    print("saved", f)
}