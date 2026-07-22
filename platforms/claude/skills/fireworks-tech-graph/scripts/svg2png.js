#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");

async function main() {
  const directory = path.resolve(process.argv[2] || ".");
  const svgFiles = fs.readdirSync(directory).filter((file) => file.endsWith(".svg"));
  const browser = await puppeteer.launch({
    headless: "new",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    for (const file of svgFiles) {
      const svgPath = path.join(directory, file);
      const pngPath = svgPath.replace(/\.svg$/, ".png");
      const svgContent = fs.readFileSync(svgPath, "utf8");
      const widthMatch = svgContent.match(/width="(\d+)/);
      const heightMatch = svgContent.match(/height="(\d+)/);
      const viewBoxMatch = svgContent.match(/viewBox="[^"]*\s(\d+)\s(\d+)"/);
      const width = widthMatch ? Number(widthMatch[1]) : viewBoxMatch ? Number(viewBoxMatch[1]) : 1200;
      const height = heightMatch ? Number(heightMatch[1]) : viewBoxMatch ? Number(viewBoxMatch[2]) : 800;
      const page = await browser.newPage();

      await page.setViewport({ width, height, deviceScaleFactor: 2 });
      await page.setContent(
        `<html><body style="margin:0;background:transparent"><img src="data:image/svg+xml;base64,${Buffer.from(svgContent).toString("base64")}" width="${width}" height="${height}"></body></html>`,
        { waitUntil: "networkidle0" },
      );
      await page.screenshot({ path: pngPath, type: "png", omitBackground: true });
      await page.close();
      console.log(`Done: ${file} -> ${path.basename(pngPath)} (${width}x${height} @2x)`);
    }
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
