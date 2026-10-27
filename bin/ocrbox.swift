// 图片 OCR + 坐标（读扫描图的坐标轴刻度、给曲线标定用）
// 编译：swiftc -O ocrbox.swift -o ocrbox
// 用法：./ocrbox <png>   → 输出 "x y w h 文本"，x/y 为左上原点像素
import Foundation
import Vision
import CoreGraphics
import AppKit

let args = CommandLine.arguments
let url = URL(fileURLWithPath: args[1])
guard let img = NSImage(contentsOf: url), let tiff = img.tiffRepresentation,
      let rep = NSBitmapImageRep(data: tiff), let cg = rep.cgImage else { exit(1) }
let W = CGFloat(cg.width), H = CGFloat(cg.height)
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["zh-Hans", "en-US"]
try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
for o in request.results ?? [] {
    guard let c = o.topCandidates(1).first else { continue }
    let b = o.boundingBox
    print(String(format: "%6.0f %6.0f %6.0f %6.0f  %@",
                 b.minX * W, (1 - b.maxY) * H, b.width * W, b.height * H, c.string))
}
