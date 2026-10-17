// C.P.S. — AI Coding Companion | Site Adapters
// ============================================================================
// Site-specific extractors for coding platforms, repositories, and Q&A sites.
// Loaded as a content script before content.js.
//
// Each adapter detects its target site, extracts problem statements and code
// from platform-specific DOM structures, and returns enriched context.
// ============================================================================

'use strict';

// ---------------------------------------------------------------------------
// Base Adapter
// ---------------------------------------------------------------------------

/**
 * Abstract base class for site adapters.
 * All adapters must implement detect(), extractProblem(), extractCode(), and getName().
 */
class SiteAdapter {
  /**
   * Checks whether this adapter handles the current hostname.
   * @param {string} hostname - e.g. "leetcode.com"
   * @returns {boolean}
   */
  detect(hostname) {
    return false;
  }

  /**
   * Returns the human-readable name of the detected site.
   * @returns {string}
   */
  getName() {
    return 'Unknown';
  }

  /**
   * Attempts to extract the problem statement from the page.
   * @returns {string} Problem text, or empty string.
   */
  extractProblem() {
    return '';
  }

  /**
   * Attempts to extract the code currently in the editor.
   * @returns {string} Code text, or empty string.
   */
  extractCode() {
    return '';
  }

  /**
   * Returns a combined context object with all extracted information.
   * @returns {{ siteName: string, problem: string, code: string }}
   */
  getContext() {
    return {
      siteName: this.getName(),
      problem: this.extractProblem(),
      code: this.extractCode(),
    };
  }

  /**
   * Helper: safely extract text content from a CSS selector.
   * @param {string} selector
   * @param {Element} [root=document]
   * @returns {string}
   */
  _getText(selector, root = document) {
    const el = root.querySelector(selector);
    return el ? this._cleanText(el.textContent) : '';
  }

  /**
   * Helper: safely extract inner HTML from a CSS selector.
   * @param {string} selector
   * @param {Element} [root=document]
   * @returns {string}
   */
  _getHTML(selector, root = document) {
    const el = root.querySelector(selector);
    return el ? el.innerHTML.trim() : '';
  }

  /**
   * Helper: strip HTML tags and normalise whitespace.
   * @param {string} html
   * @returns {string}
   */
  _stripHTML(html) {
    const div = document.createElement('div');
    div.innerHTML = String(html)
      .replace(/<br\s*\/?>(?=\s*)/gi, '\n')
      .replace(/<\/(?:p|div|li|pre|h[1-6])\s*>/gi, '\n');
    return this._cleanText(div.textContent);
  }

  /**
   * Normalises browser line endings without collapsing indentation, Unicode,
   * or meaningful whitespace inside a code sample.
   */
  _cleanText(value) {
    return String(value || '')
      .replace(/^\uFEFF/, '')
      .replace(/\r\n?/g, '\n')
      .replace(/^\n+|\n+$/g, '');
  }

  _getCode(selector, root = document) {
    const el = root.querySelector(selector);
    if (!el) return '';
    const value = typeof el.value === 'string' && el.value.length ? el.value : el.textContent;
    return this._cleanText(value);
  }

  /**
   * Helper: truncate text to a maximum length.
   * @param {string} text
   * @param {number} [maxLen=5000]
   * @returns {string}
   */
  _truncate(text, maxLen = 5000) {
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + '\n... [truncated]';
  }
}

// ---------------------------------------------------------------------------
// LeetCode Adapter
// ---------------------------------------------------------------------------

class LeetCodeAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('leetcode.com');
  }

  getName() {
    return 'LeetCode';
  }

  extractProblem() {
    // Primary selector for new LeetCode UI
    const selectors = [
      'div[data-cy="question-content"]',
      '.question-content',
      '[data-track-load="description_content"]',
      '.elfjS',                                   // React-based layout
      'meta[name="description"]',
    ];

    for (const sel of selectors) {
      if (sel.startsWith('meta')) {
        const meta = document.querySelector(sel);
        if (meta && meta.content) return this._truncate(meta.content);
        continue;
      }
      const text = this._getText(sel);
      if (text.length > 20) return this._truncate(text);
    }

    // Fallback: page title
    const title = document.title.replace(' - LeetCode', '').trim();
    return title || '';
  }

  extractCode() {
    // Monaco editor (new UI)
    const monacoTextarea = document.querySelector('.monaco-editor textarea');
    if (monacoTextarea && monacoTextarea.value) {
      return this._truncate(monacoTextarea.value);
    }

    // Monaco view lines (read-only or rendered)
    const viewLines = document.querySelectorAll('.monaco-editor .view-line');
    if (viewLines.length > 0) {
      const lines = Array.from(viewLines).map((el) => el.textContent);
      const code = lines.join('\n');
      if (code.trim().length > 5) return this._truncate(code);
    }

    // CodeMirror fallback
    const cm = document.querySelector('.CodeMirror');
    if (cm && cm.CodeMirror) {
      return this._truncate(cm.CodeMirror.getValue());
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// HackerRank Adapter
// ---------------------------------------------------------------------------

class HackerRankAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('hackerrank.com');
  }

  getName() {
    return 'HackerRank';
  }

  extractProblem() {
    const selectors = [
      '.challenge-body-html',
      '.problem-statement',
      '.challenge_problem_statement',
      '.hr_tour-problem-statement',
    ];
    for (const sel of selectors) {
      const text = this._getText(sel);
      if (text.length > 20) return this._truncate(text);
    }
    return '';
  }

  extractCode() {
    // CodeMirror
    const cm = document.querySelector('.CodeMirror');
    if (cm && cm.CodeMirror) {
      return this._truncate(cm.CodeMirror.getValue());
    }

    // Monaco editor
    const monacoTextarea = document.querySelector('.monaco-editor textarea');
    if (monacoTextarea && monacoTextarea.value) {
      return this._truncate(monacoTextarea.value);
    }

    // Fallback: .hr-monaco-editor-wrapper
    const wrapper = document.querySelector('.hr-monaco-editor-wrapper textarea');
    if (wrapper && wrapper.value) {
      return this._truncate(wrapper.value);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// Codeforces Adapter
// ---------------------------------------------------------------------------

class CodeforcesAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('codeforces.com');
  }

  getName() {
    return 'Codeforces';
  }

  extractProblem() {
    const selectors = [
      '.problem-statement',
      '.problemindexholder',
    ];
    for (const sel of selectors) {
      const text = this._getText(sel);
      if (text.length > 20) return this._truncate(text);
    }
    return '';
  }

  extractCode() {
    // Ace Editor
    const aceEditor = document.querySelector('.ace_editor');
    if (aceEditor && aceEditor.env && aceEditor.env.editor) {
      return this._truncate(aceEditor.env.editor.getValue());
    }

    // Submission code block
    const sourceCode = this._getCode('#sourceCodeTextarea');
    if (sourceCode) return this._truncate(sourceCode);

    // Textarea fallback
    const textarea = document.querySelector('#sourceCodeTextarea, textarea.source');
    if (textarea && textarea.value) return this._truncate(textarea.value);

    return '';
  }
}

// ---------------------------------------------------------------------------
// CodeChef Adapter
// ---------------------------------------------------------------------------

class CodeChefAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('codechef.com');
  }

  getName() {
    return 'CodeChef';
  }

  extractProblem() {
    const selectors = [
      '.problem-statement',
      '.problem-content',
      '#problem-statement',
      '.mathjax-support',
    ];
    for (const sel of selectors) {
      const text = this._getText(sel);
      if (text.length > 20) return this._truncate(text);
    }
    return '';
  }

  extractCode() {
    // Monaco or CodeMirror
    const monacoTextarea = document.querySelector('.monaco-editor textarea');
    if (monacoTextarea && monacoTextarea.value) {
      return this._truncate(monacoTextarea.value);
    }

    const cm = document.querySelector('.CodeMirror');
    if (cm && cm.CodeMirror) {
      return this._truncate(cm.CodeMirror.getValue());
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// GeeksForGeeks Adapter
// ---------------------------------------------------------------------------

class GeeksForGeeksAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('geeksforgeeks.org');
  }

  getName() {
    return 'GeeksForGeeks';
  }

  extractProblem() {
    const selectors = [
      '.problems_header_content__title',
      '.problem-statement',
      '.post-content',
      '.entry-content',
      'article',
    ];
    for (const sel of selectors) {
      const text = this._getText(sel);
      if (text.length > 20) return this._truncate(text);
    }
    return '';
  }

  extractCode() {
    // Ace Editor
    const aceEditor = document.querySelector('.ace_editor');
    if (aceEditor && aceEditor.env && aceEditor.env.editor) {
      return this._truncate(aceEditor.env.editor.getValue());
    }

    // CodeMirror
    const cm = document.querySelector('.CodeMirror');
    if (cm && cm.CodeMirror) {
      return this._truncate(cm.CodeMirror.getValue());
    }

    // Code blocks in articles
    const codeBlocks = document.querySelectorAll('pre code, .code-container code');
    if (codeBlocks.length > 0) {
      const code = Array.from(codeBlocks)
        .map((el) => this._cleanText(el.textContent))
        .filter((t) => t.length > 5)
        .join('\n\n');
      if (code) return this._truncate(code);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// GitHub Adapter
// ---------------------------------------------------------------------------

class GitHubAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('github.com');
  }

  getName() {
    return 'GitHub';
  }

  extractProblem() {
    // Issue body
    const issueBody = this._getText('.js-comment-body');
    if (issueBody.length > 20) return this._truncate(issueBody);

    // PR description
    const prBody = this._getText('.comment-body');
    if (prBody.length > 20) return this._truncate(prBody);

    // README
    const readme = this._getText('#readme article');
    if (readme.length > 20) return this._truncate(readme);

    return '';
  }

  extractCode() {
    // File blob view
    const blobLines = document.querySelectorAll('.blob-code-inner');
    if (blobLines.length > 0) {
      const code = Array.from(blobLines).map((el) => el.textContent).join('\n');
      if (code.trim().length > 5) return this._truncate(code);
    }

    // Code block in markdown
    const codeBlocks = document.querySelectorAll('.highlight pre, pre code');
    if (codeBlocks.length > 0) {
      const code = Array.from(codeBlocks)
        .map((el) => this._cleanText(el.textContent))
        .filter((t) => t.length > 5)
        .join('\n\n');
      if (code) return this._truncate(code);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// GitLab Adapter
// ---------------------------------------------------------------------------

class GitLabAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('gitlab.com') || hostname.includes('gitlab.');
  }

  getName() {
    return 'GitLab';
  }

  extractProblem() {
    // Issue / MR description
    const description = this._getText('.description .md');
    if (description.length > 20) return this._truncate(description);

    // Note body
    const noteBody = this._getText('.note-body .md');
    if (noteBody.length > 20) return this._truncate(noteBody);

    return '';
  }

  extractCode() {
    // File blob
    const blobLines = document.querySelectorAll('.blob-content .line');
    if (blobLines.length > 0) {
      const code = Array.from(blobLines).map((el) => el.textContent).join('\n');
      if (code.trim().length > 5) return this._truncate(code);
    }

    // Code blocks
    const codeBlocks = document.querySelectorAll('pre code');
    if (codeBlocks.length > 0) {
      const code = Array.from(codeBlocks)
        .map((el) => this._cleanText(el.textContent))
        .filter((t) => t.length > 5)
        .join('\n\n');
      if (code) return this._truncate(code);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// StackOverflow Adapter
// ---------------------------------------------------------------------------

class StackOverflowAdapter extends SiteAdapter {
  detect(hostname) {
    return hostname.includes('stackoverflow.com') || hostname.includes('stackexchange.com');
  }

  getName() {
    return 'StackOverflow';
  }

  extractProblem() {
    // Question body
    const question = this._getText('.s-prose');
    if (question.length > 20) return this._truncate(question);

    // Fallback
    const postBody = this._getText('.post-text');
    if (postBody.length > 20) return this._truncate(postBody);

    return '';
  }

  extractCode() {
    // Code blocks in question and answers
    const codeBlocks = document.querySelectorAll('.s-prose pre code, .post-text pre code');
    if (codeBlocks.length > 0) {
      const code = Array.from(codeBlocks)
        .map((el) => this._cleanText(el.textContent))
        .filter((t) => t.length > 5)
        .join('\n\n---\n\n');
      if (code) return this._truncate(code);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// Generic Adapter (Fallback)
// ---------------------------------------------------------------------------

class GenericAdapter extends SiteAdapter {
  detect(_hostname) {
    // Always matches — used as fallback
    return true;
  }

  getName() {
    // Derive a name from the hostname
    try {
      const hostname = window.location.hostname.replace('www.', '');
      return hostname.charAt(0).toUpperCase() + hostname.slice(1);
    } catch {
      return 'Website';
    }
  }

  extractProblem() {
    // Use the current selection if available
    const sel = window.getSelection();
    if (sel && sel.toString().trim().length > 3) {
      return this._truncate(sel.toString().trim());
    }

    // Fallback: page title + meta description
    const metaDesc = document.querySelector('meta[name="description"]');
    const desc = metaDesc ? metaDesc.content : '';
    const title = document.title || '';
    const combined = `${title}\n${desc}`.trim();
    return combined || '';
  }

  extractCode() {
    // Try editor buffers first, then rendered code blocks.  Reading `.value`
    // is important for plain textareas because their textContent is empty.
    const editor = document.querySelector('textarea:not([aria-hidden="true"]), [contenteditable="true"]');
    if (editor) {
      const value = typeof editor.value === 'string' ? editor.value : editor.textContent;
      const code = this._cleanText(value);
      if (code.trim().length > 5) return this._truncate(code);
    }

    const codeBlocks = document.querySelectorAll('pre code, pre, code, .highlight pre');
    if (codeBlocks.length > 0) {
      const code = Array.from(codeBlocks)
        .map((el) => this._cleanText(el.textContent))
        .filter((t) => t.length > 10)
        .slice(0, 5)
        .join('\n\n');
      if (code) return this._truncate(code);
    }

    return '';
  }
}

// ---------------------------------------------------------------------------
// Adapter Registry
// ---------------------------------------------------------------------------

/**
 * Registry that automatically selects the appropriate adapter for the current page.
 */
class AdapterRegistry {
  constructor() {
    this._adapters = [
      new LeetCodeAdapter(),
      new HackerRankAdapter(),
      new CodeforcesAdapter(),
      new CodeChefAdapter(),
      new GeeksForGeeksAdapter(),
      new GitHubAdapter(),
      new GitLabAdapter(),
      new StackOverflowAdapter(),
    ];
    this._fallback = new GenericAdapter();
  }

  /**
   * Returns the best adapter for the given hostname.
   * @param {string} hostname
   * @returns {SiteAdapter}
   */
  getAdapter(hostname) {
    const lower = (hostname || '').toLowerCase();
    for (const adapter of this._adapters) {
      if (adapter.detect(lower)) {
        return adapter;
      }
    }
    return this._fallback;
  }
}

// ---------------------------------------------------------------------------
// Public API (global scope for content script access)
// ---------------------------------------------------------------------------

const _cpsAdapterRegistry = new AdapterRegistry();

/**
 * Returns the appropriate site adapter for the given hostname.
 * @param {string} [hostname=window.location.hostname]
 * @returns {SiteAdapter}
 */
function getAdapter(hostname) {
  return _cpsAdapterRegistry.getAdapter(hostname || window.location.hostname);
}

// Expose globally for content.js
window._cpsGetAdapter = getAdapter;
window._cpsAdapterRegistry = _cpsAdapterRegistry;
