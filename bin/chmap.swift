// 从整本扫描书每页页眉条识别「第N章」+ 印刷页码 → 章节地图 JSONL
// 编译：swiftc -O chmap.swift -o chmap
// 用法：./chmap <book.pdf> > chmap.jsonl
// 说明：页眉在切口侧（奇偶页左右互换），故上下各扫一条；.accurate 才能认出小字。
import Foundation
import PDFKit
import Vision
import CoreGraphics
import AppKit

let args = CommandLine.arguments
guard args.count >= 2, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    print("usage: chmap <book.pdf>"); exit(1)
}
FileHandle.standardError.write("pages: \(doc.pageCount)\n".data(using: .utf8)!)

let chRe = try! NSRegularExpression(pattern: #"第\s*([0-9]{1,2})\s*[\.．。]?\s*章"#)
let pgRe = try! NSRegularExpression(pattern: #"([0-9]{2,3})\s*$"#)

func ocr(_ img: CGImage) -> String {
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    try? VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
    return (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: " ")
}

for i in 0..<doc.pageCount {
    guard let page = doc.page(at: i) else { continue }
    let rect = page.bounds(for: .mediaBox)
    let scale: CGFloat = 4.0
    let w = Int(rect.width * scale), h = Int(rect.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { continue }
    ctx.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    guard let full = ctx.makeImage() else { continue }

    let bandH = Int(Double(h) * 0.09)
    var texts: [String] = []
    for y0 in [0, h - bandH] {
        if let band = full.cropping(to: CGRect(x: 0, y: y0, width: w, height: bandH)) {
            texts.append(ocr(band))
        }
    }
    let joined = texts.joined(separator: "  ‖  ")

    var ch: Int? = nil
    if let m = chRe.firstMatch(in: joined, range: NSRange(joined.startIndex..., in: joined)) {
        // 取第一个匹配；个别页眉 OCR 成「第10.章」，正则已容错
        let s = (joined as NSString).substring(with: m.range(at: 1))
        ch = Int(s)
    }
    var printed: Int? = nil
    for part in texts {
        if let m = pgRe.firstMatch(in: part, range: NSRange(part.startIndex..., in: part)) {
            printed = Int((part as NSString).substring(with: m.range(at: 1)))
            break
        }
    }

    let payload: [String: Any] = [
        "pdf": i + 1,
        "ch": (ch as Any?) ?? NSNull(),
        "printed": (printed as Any?) ?? NSNull(),
        "head": String(joined.prefix(120))
    ]
    if let d = try? JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys]),
       let s = String(data: d, encoding: .utf8) { print(s) }
}
