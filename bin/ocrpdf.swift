// 扫描版教材 PDF → 逐页中文 OCR（macOS Vision，离线）
// 编译：swiftc -O ocrpdf.swift -o ocrpdf
// 用法：./ocrpdf <pdf> <首页> <末页> <输出目录>   页码从 1 开始
import Foundation
import PDFKit
import Vision
import CoreGraphics
import AppKit

let args = CommandLine.arguments
guard args.count >= 5 else { print("usage: ocrpdf <pdf> <first> <last> <outdir>"); exit(1) }
let url = URL(fileURLWithPath: args[1])
let first = Int(args[2]) ?? 1
let last = Int(args[3]) ?? 1
let outdir = URL(fileURLWithPath: args[4])
try? FileManager.default.createDirectory(at: outdir, withIntermediateDirectories: true)

guard let doc = PDFDocument(url: url) else { print("cannot open"); exit(1) }
print("pages: \(doc.pageCount)")

for i in max(0, first-1)..<min(doc.pageCount, last) {
    guard let page = doc.page(at: i) else { continue }
    let rect = page.bounds(for: .mediaBox)
    let scale: CGFloat = 3.0
    let w = Int(rect.width * scale), h = Int(rect.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let img = ctx.makeImage() else { continue }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    let handler = VNImageRequestHandler(cgImage: img, options: [:])
    do { try handler.perform([request]) } catch { print("ocr fail page \(i+1): \(error)"); continue }
    guard let obs = request.results else { continue }

    var lines: [(CGFloat, CGFloat, String)] = []
    for o in obs {
        guard let c = o.topCandidates(1).first else { continue }
        let bb = o.boundingBox
        lines.append((1.0 - bb.maxY, bb.minX, c.string))  // 转成左上原点
    }
    lines.sort { a, b in abs(a.0 - b.0) < 0.008 ? a.1 < b.1 : a.0 < b.0 }
    var out = ""
    var lastY: CGFloat = -1
    for (y, _, s) in lines {
        out += (lastY >= 0 && abs(y - lastY) < 0.008) ? "  " + s : "\n" + s
        lastY = y
    }
    let f = outdir.appendingPathComponent(String(format: "p%03d.txt", i+1))
    try? out.write(to: f, atomically: true, encoding: .utf8)
    print("page \(i+1) done, \(lines.count) lines")
}
