/* One shared local query + brief implementation for browser and Node.
 *
 * This is deterministic lexical retrieval over curated prose and triggers.
 * It performs no model inference, no network access, no logging and no
 * persistence: callers pass canonical data in and get plain results out.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Practice = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const READER_BASE = 'https://indeliblevivi.github.io/agent-memory-study/';

  // Public repo-relative files resolve to a portable absolute URL. HTTPS URLs
  // are already portable and are returned unchanged.
  function portableUrl(url) {
    if (typeof url !== 'string' || !url) return url;
    if (/^https:\/\//i.test(url)) return url;
    if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return url;
    const hashAt = url.indexOf('#');
    const base = hashAt >= 0 ? url.slice(0, hashAt) : url;
    const fragment = hashAt >= 0 ? url.slice(hashAt) : '';
    return READER_BASE + base + fragment;
  }

  function normalize(value) {
    return String(value ?? '').normalize('NFKC').toLocaleLowerCase('zh-CN').replace(/\s+/gu, ' ').trim();
  }

  const ENGLISH_STOP_WORDS = new Set([
    'a', 'an', 'and', 'or', 'the', 'is', 'are', 'was', 'were', 'be', 'been',
    'do', 'does', 'did', 'to', 'of', 'in', 'on', 'at', 'for', 'with', 'from',
    'how', 'what', 'where', 'when', 'why', 'which', 'before', 'after',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'this', 'that',
    'can', 'could', 'should', 'would', 'will', 'please',
  ]);
  const CJK = /[\u3400-\u9fff\uf900-\ufaff]/;

  // A forgiving lexical query: Latin words (length >= 2) plus, for every CJK
  // run, the run itself and its overlapping bigrams (length >= 2). Single
  // characters are dropped so a stray syllable cannot match by accident. Units
  // are unique and keep first-seen order, so repeated text adds no rank.
  function queryUnits(text) {
    const normalized = normalize(text);
    const units = [];
    const seen = new Set();
    const push = unit => {
      if (unit.length < 2 || seen.has(unit) || ENGLISH_STOP_WORDS.has(unit)) return;
      seen.add(unit);
      units.push(unit);
    };
    let i = 0;
    while (i < normalized.length) {
      const char = normalized[i];
      if (CJK.test(char)) {
        let run = '';
        while (i < normalized.length && CJK.test(normalized[i])) {
          run += normalized[i];
          i += 1;
        }
        push(run);
        for (let j = 0; j + 1 < run.length; j += 1) push(run.slice(j, j + 2));
        continue;
      }
      if (/[a-z0-9]/.test(char)) {
        let word = '';
        while (i < normalized.length && /[a-z0-9'-]/.test(normalized[i])) {
          word += normalized[i];
          i += 1;
        }
        push(word.replace(/^[-']+|[-']+$/g, ''));
        continue;
      }
      i += 1;
    }
    return units;
  }

  function tokenize(text) {
    return queryUnits(text);
  }

  // Curated triggers are the anchors; the title is next; the remaining prose is
  // weaker context. Weights are small, fixed and model-free.
  const TRIGGER_WEIGHT = 6;
  const TITLE_WEIGHT = 4;
  const PROSE_WEIGHT = 2;
  const MAX_RESULTS = 3;

  function proseText(finding) {
    const parts = [finding.claim, finding.when, finding.action, finding.avoid,
      finding.validation, finding.limit];
    (finding.evidence || []).forEach(item => parts.push(item.label, item.observation, item.limit));
    (finding.applications || []).forEach(item =>
      parts.push(item.title, item.decision, item.observation, item.limit));
    return normalize(parts.filter(part => typeof part === 'string').join(' '));
  }

  function lexicalText(text) {
    const normalized = normalize(text);
    const words = new Set(normalized.match(/[a-z0-9]+(?:[-'][a-z0-9]+)*/g) || []);
    return unit => CJK.test(unit) ? normalized.includes(unit) : words.has(unit);
  }

  // Each distinct query unit is counted once, credited at the strongest tier it
  // reaches. Repeated text in the finding or the query cannot add rank.
  function scoreFinding(finding, units) {
    const triggers = lexicalText((finding.triggers || []).join(" "));
    const title = lexicalText(finding.title);
    const prose = lexicalText(proseText(finding));
    let score = 0;
    const matches = [];
    for (const unit of units) {
      if (triggers(unit)) {
        score += TRIGGER_WEIGHT;
        matches.push(unit);
      } else if (title(unit)) {
        score += TITLE_WEIGHT;
        matches.push(unit);
      } else if (prose(unit)) {
        score += PROSE_WEIGHT;
        matches.push(unit);
      }
    }
    return {score, matches};
  }

  function list(data, key) {
    return Array.isArray(data && data[key]) ? data[key] : [];
  }

  function query(data, q, limit = MAX_RESULTS) {
    const findings = list(data, 'findings').filter(item => item && typeof item === 'object');
    const bounded = Math.min(
      Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 0,
      MAX_RESULTS,
    );
    if (!bounded) return [];
    const units = queryUnits(q);
    // An empty or whitespace-only query browses the first findings with no score.
    // A non-empty query that yields no lexical units (for example punctuation)
    // matches nothing rather than dumping the whole inventory.
    if (!normalize(q)) {
      return findings.slice(0, bounded)
        .map(finding => ({finding, score: 0, matches: []}));
    }
    if (!units.length) return [];
    const scored = [];
    findings.forEach((finding, order) => {
      const {score, matches} = scoreFinding(finding, units);
      if (score > 0) scored.push({finding, score, matches, order});
    });
    // Score ties break on canonical declaration order for determinism.
    return scored
      .sort((a, b) => b.score - a.score || a.order - b.order)
      .slice(0, bounded)
      .map(entry => ({finding: entry.finding, score: entry.score, matches: entry.matches}));
  }

  function findFinding(data, findingId) {
    const finding = list(data, 'findings').find(item => item && item.id === findingId);
    if (!finding) throw new Error(`Unknown finding id: ${String(findingId)}`);
    return finding;
  }

  function portableFinding(finding) {
    const viewer = (key, id) => `${READER_BASE}?${key}=${encodeURIComponent(id)}`;
    return {
      ...finding,
      evidence: (finding.evidence || []).map(item => ({...item, url: portableUrl(item.url)})),
      applications: (finding.applications || []).map(item => ({...item, url: portableUrl(item.url)})),
      readerUrl: viewer('finding', finding.id),
      materialLinks: (finding.materialIds || []).map(id => ({id, url: viewer('material', id)})),
      questionLinks: (finding.questionIds || []).map(id => ({id, url: viewer('question', id)})),
    };
  }

  function brief(data, q, options = {}) {
    const {limit = 3, findingId = null} = options;
    let findings;
    if (findingId) {
      // Exact selection by canonical id, no ranking.
      findings = [findFinding(data, findingId)];
    } else {
      findings = query(data, q, limit).map(hit => hit.finding);
    }
    const boundary = {
      method: 'lexical',
      ranking: findingId ? 'none (exact canonical id)' : 'distinct trigger/title/prose matches',
      inference: 'none',
      persistence: 'none',
      network: 'none',
      note: 'Local forgiving lexical matching over curated triggers and prose. Not semantic search and not a judgment about effect.',
    };
    return {
      query: q,
      method: 'local-lexical-query',
      browse: !findingId && !normalize(q),
      boundary,
      findings: findings.map(portableFinding),
    };
  }

  function line(label, value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    return `- **${label}**: ${value}`;
  }

  function markdown(briefing) {
    const out = [];
    out.push('# Practice brief');
    out.push('');
    const queryLabel = briefing.query && briefing.query.trim()
      ? briefing.query
      : (briefing.browse ? '(empty query: first findings, no ranking)' : '(exact finding export)');
    out.push(`- **Query**: ${queryLabel}`);
    const ranking = findingIdLabel(briefing.boundary.ranking);
    out.push(`- **Method**: ${briefing.method} (${ranking}; no inference, no persistence, no network)`);
    out.push(`- **Boundary**: ${briefing.boundary.note}`);
    if (!briefing.findings.length) {
      out.push('');
      out.push('_No finding matched this query. That is not evidence the question is unstudied._');
      return out.join('\n') + '\n';
    }
    for (const finding of briefing.findings) {
      out.push('');
      out.push(`## ${finding.title}`);
      out.push('');
      out.push(`- **Status**: ${finding.status}`);
      out.push(`- **Byline**: ${finding.byline}`);
      out.push(`- **Updated**: ${finding.updated}`);
      out.push(`- **Reader**: ${finding.readerUrl}`);
      if (finding.materialLinks && finding.materialLinks.length) {
        out.push(`- **Materials**: ${finding.materialLinks.map(link => `[${link.id}](${link.url})`).join(', ')}`);
      }
      if (finding.questionLinks && finding.questionLinks.length) {
        out.push(`- **Questions**: ${finding.questionLinks.map(link => `[${link.id}](${link.url})`).join(', ')}`);
      }
      if (finding.triggers && finding.triggers.length) {
        out.push(`- **Triggers**: ${finding.triggers.join(' · ')}`);
      }
      out.push('');
      [['Claim', finding.claim], ['When', finding.when], ['Action', finding.action],
       ['Avoid', finding.avoid], ['Validation', finding.validation], ['Limit', finding.limit]]
        .map(([label, value]) => line(label, value))
        .filter(Boolean)
        .forEach(row => out.push(row));
      if (finding.evidence && finding.evidence.length) {
        out.push('');
        out.push('### Evidence');
        for (const item of finding.evidence) {
          out.push(`- **[${item.label}](${item.url})**`);
          out.push(`  - Observation: ${item.observation}`);
          out.push(`  - Limit: ${item.limit}`);
        }
      }
      if (finding.applications && finding.applications.length) {
        out.push('');
        out.push('### Applications');
        for (const item of finding.applications) {
          out.push(`- **[${item.title}](${item.url})** — ${item.status} (${item.date})`);
          out.push(`  - Decision: ${item.decision}`);
          out.push(`  - Observation: ${item.observation}`);
          out.push(`  - Limit: ${item.limit}`);
        }
      }
    }
    return out.join('\n') + '\n';
  }

  function findingIdLabel(ranking) {
    return ranking === 'none (exact canonical id)' ? 'exact canonical id, no ranking' : ranking;
  }

  return {query, brief, markdown, normalize, tokenize, portableUrl};
});
