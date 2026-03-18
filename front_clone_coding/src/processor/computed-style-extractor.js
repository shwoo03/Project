import logger from '../utils/logger.js';

export default class ComputedStyleExtractor {
  static async extract(page) {
    logger.start('Extracting computed style snapshots');

    try {
      const result = await Promise.race([
        page.evaluate(() => {
          const output = { dynamicSheets: [], cssInJsStyles: [] };

          try {
            const styleTags = document.querySelectorAll('style');
            for (const node of styleTags) {
              let source = null;

              for (const attribute of node.attributes) {
                const attrName = attribute.name;
                if (
                  attrName.startsWith('data-styled') ||
                  attrName.startsWith('data-emotion') ||
                  attrName.startsWith('data-jss') ||
                  attrName.startsWith('sc-')
                ) {
                  source = attrName;
                  break;
                }
              }

              const css = node.textContent || '';
              if (source || css.trim()) {
                output.cssInJsStyles.push({
                  css,
                  source: source || 'dynamic',
                });
              }
            }
          } catch {
            // Ignore DOM extraction errors and keep the crawl moving.
          }

          return output;
        }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('CSS extraction timeout')), 3000)),
      ]);

      const totalExtracted = result.cssInJsStyles.length + result.dynamicSheets.length;
      if (totalExtracted > 0) {
        logger.succeed(
          `Computed style extraction complete: ${result.cssInJsStyles.length} CSS-in-JS block(s), ${result.dynamicSheets.length} dynamic stylesheet(s)`,
        );
      } else {
        logger.succeed('Computed style extraction complete: no dynamic styles detected');
      }

      return result;
    } catch {
      logger.succeed('Computed style extraction skipped');
      return { dynamicSheets: [], cssInJsStyles: [] };
    }
  }

  static injectIntoHtml($, extractedCss) {
    if (!extractedCss) return;

    const { cssInJsStyles, dynamicSheets } = extractedCss;
    for (const { css, source } of cssInJsStyles) {
      $('head').append(`\n    <style data-extracted-from="${source}">\n${css}\n    </style>`);
    }

    for (const css of dynamicSheets) {
      $('head').append(`\n    <style data-extracted-from="dynamic-sheet">\n${css}\n    </style>`);
    }
  }
}
