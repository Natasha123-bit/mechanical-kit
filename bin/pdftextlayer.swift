// Probe a PDF's text layer before deciding whether OCR is needed.
//
// Build once:  swiftc -O pdftextlayer.swift -o pdftextlayer
// Run:         ./pdftextlayer book.pdf            # first / middle / last page
//              ./pdftextlayer book.pdf 3 16 30     # specific zero-based page indexes
//
// Read the output like this:
//   chars=0            -> pure scan, OCR required (renderall.swift + ocrpdf.swift)
//   chars>0 but mojibake (`W-tiWlW`, `$n[^I io-5`) -> broken CID map, OCR required
//   readable Chinese/math -> text layer is usable, grep 例/表10-/图10- directly
// The number of /Font objects in the raw bytes is NOT evidence either way.

import Foundation
import PDFKit

let args = CommandLine.arguments
let usage = "usage: pdftextlayer <file.pdf> [pageIndex ...]"

guard args.count >= 2, let doc = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    print(usage)
    exit(1)
}

print("file: \(args[1])")
print("pages: \(doc.pageCount)")

var targets = Array(args.dropFirst(2)).compactMap { Int($0) }
if targets.isEmpty {
    var t = [0, doc.pageCount / 2, doc.pageCount - 1]
    if doc.pageCount > 3 { t.append(3) }
    targets = t
}

var readable = 0
var scanned = 0

for i in targets where i >= 0 && i < doc.pageCount {
    let s = doc.page(at: i)?.string ?? ""
    let head = String(s.prefix(90)).replacingOccurrences(of: "\n", with: " | ")
    print("page \(i): chars=\(s.count)  \(head)")
    if s.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { scanned += 1 } else { readable += 1 }
}

if readable == 0 && scanned > 0 {
    print("verdict: no text layer on the sampled pages -> OCR the whole book")
} else if scanned > 0 {
    print("verdict: mixed - some sampled pages are scans, OCR those pages only")
} else {
    print("verdict: text present - eyeball the sample lines above; mojibake means OCR anyway")
}
