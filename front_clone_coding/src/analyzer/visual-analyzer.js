import path from 'path';
import * as cheerio from 'cheerio';
import { ensureDir, saveFile } from '../utils/file-utils.js';

const COLOR_REGEX = /#(?:[0-9a-fA-F]{3,8})\b|rgba?\([^)]+\)|hsla?\([^)]+\)/g;
const FONT_REGEX = /font-family\s*:\s*([^;}{]+)/gi;
const CSS_VAR_REGEX = /--([\w-]+)\s*:\s*([^;]+);/g;

export default class VisualAnalyzer {
  constructor(outputDir) {
    this.outputDir = outputDir;
  }

  async generate(pages) {
    const docsDir = path.join(this.outputDir, 'server', 'docs', 'ui');
    const screensDir = path.join(docsDir, 'screens');
    await ensureDir(docsDir);
    await ensureDir(screensDir);

    const componentInventory = [];
    const layoutLines = ['# Layout Report', ''];
    const designTokens = {
      colors: new Set(),
      fonts: new Set(),
      cssVariables: {},
    };
    const missingBehaviors = [];

    for (const page of pages) {
      const $ = cheerio.load(page.html || '', { decodeEntities: false });
      const pagePath = page.savedPath || '';
      const host = page.host || 'site';
      const screenFile = page.screenshotPath || null;

      componentInventory.push({
        pageUrl: page.finalUrl || page.url,
        savedPath: pagePath,
        title: page.title || $('title').text() || '',
        counts: {
          sections: $('section').length,
          buttons: $('button, [role="button"], input[type="button"], input[type="submit"]').length,
          forms: $('form').length,
          images: $('img').length,
          navs: $('nav').length,
          dialogs: $('[role="dialog"], dialog').length,
          videos: $('video').length,
        },
      });

      const styleText = $('style').map((_, el) => $(el).html() || '').get().join('\n');
      const inlineStyleText = $('[style]').map((_, el) => $(el).attr('style') || '').get().join('\n');
      const fullStyleText = `${styleText}\n${inlineStyleText}\n${this._computedCssText(page.computedStyles)}`;

      for (const color of fullStyleText.match(COLOR_REGEX) || []) {
        designTokens.colors.add(color);
      }

      let match;
      FONT_REGEX.lastIndex = 0;
      while ((match = FONT_REGEX.exec(fullStyleText)) !== null) {
        designTokens.fonts.add(match[1].trim());
      }

      CSS_VAR_REGEX.lastIndex = 0;
      while ((match = CSS_VAR_REGEX.exec(fullStyleText)) !== null) {
        designTokens.cssVariables[`--${match[1]}`] = match[2].trim();
      }

      layoutLines.push(`## ${page.title || page.finalUrl || page.url}`);
      layoutLines.push(`- Saved path: \`${pagePath}\``);
      layoutLines.push(`- Host: \`${host}\``);
      layoutLines.push(`- Sections: ${$('section').length}`);
      layoutLines.push(`- Buttons: ${$('button, [role="button"], input[type="button"], input[type="submit"]').length}`);
      layoutLines.push(`- Forms: ${$('form').length}`);
      layoutLines.push(`- Images: ${$('img').length}`);
      if (screenFile) {
        layoutLines.push(`- Screenshot: \`${screenFile}\``);
      }
      layoutLines.push('');

      if ($('[role="dialog"], dialog').length > 0) {
        missingBehaviors.push({
          pageUrl: page.finalUrl || page.url,
          hint: 'Dialog or modal behavior likely needs manual state wiring.',
        });
      }
      if ($('[data-testid*="carousel"], .carousel, .slider, [aria-roledescription="carousel"]').length > 0) {
        missingBehaviors.push({
          pageUrl: page.finalUrl || page.url,
          hint: 'Carousel or slider behavior should be reimplemented on the final frontend.',
        });
      }
      if ((page.interactiveElements || []).some((item) => item.hasOnClick)) {
        missingBehaviors.push({
          pageUrl: page.finalUrl || page.url,
          hint: 'Inline click handlers were detected and need manual reconstruction.',
        });
      }
    }

    await saveFile(
      path.join(docsDir, 'component-inventory.json'),
      JSON.stringify(componentInventory, null, 2),
    );
    await saveFile(
      path.join(docsDir, 'layout-report.md'),
      layoutLines.join('\n'),
    );
    await saveFile(
      path.join(docsDir, 'design-tokens.json'),
      JSON.stringify({
        colors: [...designTokens.colors].sort(),
        fonts: [...designTokens.fonts].sort(),
        cssVariables: designTokens.cssVariables,
      }, null, 2),
    );
    await saveFile(
      path.join(docsDir, 'missing-behaviors.md'),
      this._formatMissingBehaviors(missingBehaviors),
    );
  }

  _computedCssText(computedStyles) {
    if (!computedStyles) return '';
    const cssInJs = (computedStyles.cssInJsStyles || []).map((item) => item.css).join('\n');
    const dynamicSheets = (computedStyles.dynamicSheets || []).join('\n');
    return `${cssInJs}\n${dynamicSheets}`;
  }

  _formatMissingBehaviors(items) {
    const lines = ['# Missing Behaviors', ''];
    if (items.length === 0) {
      lines.push('No obvious JS-dependent behaviors were detected from deterministic heuristics.');
      return lines.join('\n');
    }

    for (const item of items) {
      lines.push(`- ${item.pageUrl}: ${item.hint}`);
    }
    return lines.join('\n');
  }
}
