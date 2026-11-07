/*
 * Code_RAD-ICAL_Header:
 *   Code_File:        sgc-top-status-bar.ts
 *   Code_Description: <sgc-top-status-bar> Lit Custom Element — Tier 1
 *                     global frame chrome per SPEC-NAV-01 §2.1. Replaces
 *                     the inline .titlebar section from the monolithic
 *                     sgc-app-shell.ts. Carries 3 zones:
 *                       Left:   SGC brand + day-state submode indicator
 *                       Centre: Escalation banner slot (empty at v0.1)
 *                       Right:  4 indicator placeholders + window controls
 *                     Subscribes to DayStateController for live submode
 *                     display. data-tauri-drag-region for window dragging.
 *
 *   Service_Type:     P-Series (Tier 1 — Global Frame)
 *   Code_Author:      Ghanima <ghanima@selectiongradient.capital>
 *   Code_Created:     2026-05-21
 *   Code_Modified:    2026-10-07
 *   Code_Version:     0.6.0
 *   Code_Licence:     Proprietary
 *   Code_RAD-ICAL_Classifiers:  🐻
 *   Code_RAD-ICAL_Classifier_Changes:
 *     [2026-10-07] 0.6.0: Ghanima — AM instruction of the day: the Curation step's icon is the navbar's Cockpit
 *       dartboard, the same asset (`NAV_ICON.cockpit`, assets/nav), replacing the target emoji. A step may now
 *       carry an `icon` (a data URI drawn as an `<img>`, alt "", not draggable) in place of a `glyph`; the
 *       other four steps keep their emoji. `.step-icon` is 14px: the dartboard fills the lower-left
 *       two-thirds of its box, so it reads at the 11px emoji's size.
 *     [2026-10-07] 0.5.1: Ghanima — QD261007155714 (AM 2026-10-07: blue action buttons write white in both themes, from the global token). `.theme-toggle:hover`, the blue hover of the theme switch writes its label in
 *       `--text-on-accent` (was `var(--text-inverse)`), so the token governs it. No other change.
 *     [2026-08-27] 0.5.0: Ghanima — QD260827192816 (AM directive, following a read-only review of
 *       Irulan's brand asset). The logo is the ONLY door to the About dialog and it was a plain
 *       `<div>` with a click handler — no role, no tabindex, no key handler — so About was
 *       mouse-only while `cursor: pointer` advertised otherwise. That is SKILL.md §2.7 inverted:
 *       the cursor is a promise, and here it was half-kept. Now a real `<button type="button">`,
 *       which buys role, focus and Enter/Space with no moving parts, plus a system focus ring
 *       (`outline: 2px solid Highlight`) rather than a branded one. The `<img>` drops to
 *       `alt=""` so the button owns a SINGLE accessible name instead of competing with it.
 *       `background: #ffffff` becomes `var(--brand-plate)`: the value was right and load-bearing,
 *       but a bare literal records it while losing the reason a future reader needs.
 *     [2026-08-12] 0.4.0: Ghanima — Mission-034 P401 (COMM-ghanima-260812082711). The day-state
 *       pipeline gains the 'curation' step (🎯, between Briefing and Gate — P401 declares the
 *       risk intent T400 adjudicates), and the briefing⇄curation PAIR becomes clickable as the
 *       Curation Studio's entry/exit affordance (`_stepNavTarget`/`_onStepClick`). Deliberately
 *       ONLY that pair: the Gate is lock-scoped (a clickable Gate step would open a dead Gate
 *       with no candidate — the S2-07 stranding class) and monitor/eod entry semantics are
 *       untouched. Declared in the COMM close-out: the COMM commissioned no navigation, but a
 *       surface with no door cannot meet its own renders-in-shell DoD.
 *     [2026-05-21] 0.1.0: Ghanima — Mission-008 Sprint 2 Phase 2.
 *     [2026-05-21] 0.3.0: Irulan — Mission-008 Sprint 6 (S6) theme
 *       toggle button wired between indicators and window controls.
 *       Subscribes to onThemeChange via theme-controller.
 *     [2026-05-21] 0.3.1: Ghanima — Mission-008 Sprint 6 hardening
 *       (COMM-ghanima-260521181715). Removed three anti-telltale §2.7
 *       CSS transitions: `.submode-indicator { transition: opacity }`,
 *       `.submode-glyph { transition: opacity }`, and `.theme-toggle
 *       { transition: background, color }`. Native desktop applies
 *       hover highlights instantly; transitions create a perceptible
 *       web lag (Raycast anti-telltale lineage). Deduplicated the
 *       `.indicator-dot.ok` rule (was defined twice — once setting
 *       background, once setting animation; second declaration was
 *       overriding the first's background due to cascade specificity).
 *       Aligned stale fallback hex values (#5090F0, #34D399) to
 *       current theme.css v0.3.0 token values (#4f8eff, #3fb950).
 */
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { dayState, type TodaySubmode } from '../controllers/day-state.ts';
import { getTheme, toggleTheme, onThemeChange, type Theme } from '../controllers/theme-controller.ts';
import { INFINIX_BRAND_LOGO_DATA_URI } from '../assets/infinix-brand-logo.ts';
import { STEP_ICON } from '../assets/nav/infinix-subtab-icons.ts';
import '../components/sgc-about-splash-modal.ts';













/** Submode sequence in happy-path order. */
const SUBMODES: readonly TodaySubmode[] = ['briefing', 'curation', 'gate', 'monitor', 'eod'];

/**
 * Submode display config — Tier 6 Haute-Couture vector marks (Scytale 2026-10-24).
 * Replaces legacy scaffold emojis with bespoke resolution-independent SVGs.
 */
const SUBMODE_DISPLAY: Record<TodaySubmode, { icon: string; label: string }> = {
  briefing: { icon: STEP_ICON.briefing, label: 'Briefing' },
  curation: { icon: STEP_ICON.curation, label: 'Curation' },
  gate:     { icon: STEP_ICON.gate,     label: 'Gate' },
  monitor:  { icon: STEP_ICON.monitor,  label: 'Monitor' },
  eod:      { icon: STEP_ICON.eod,      label: 'EOD' },
};


@customElement('sgc-top-status-bar')
export class SgcTopStatusBar extends LitElement {
  @state() private submode: TodaySubmode = 'briefing';
  @state() private theme: Theme = getTheme();
  @state() private _aboutOpen = false;

  private _unsubDay?: () => void;
  private _unsubTheme?: () => void;

  static styles = css`
    :host {
      display: flex;
      align-items: center;
      height: 36px;
      background: var(--surface-secondary);
      border-bottom: 1px solid var(--border-subtle);
      user-select: none;
      flex-shrink: 0;
      overflow: hidden;
    }

    /* ── Left zone: brand + submode ─────────────────────────────── */
    .drag-region {
      flex: 1;
      height: 100%;
      padding: 0 12px 0 4px;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      color: var(--text-secondary);
      cursor: default;
    }
    /* QD260827192816 — a real <button>, not a div with a click handler. It is the only door to
       the About dialog, so a mouse-only affordance made About unreachable from the keyboard and
       gave a screen reader a name with no role to act on. As a button it is focusable, Enter/Space
       activate it for free, and the pointer cursor is now unambiguously correct under SKILL.md 2.7
       rather than an exception to it. The reset below strips the UA chrome; nothing else about the
       plate changed. (No backticks in this comment - SKILL.md 2.7b. One slipped in on the first
       draft of this very block and closed the template literal; esbuild reported it as a missing
       semicolon eleven lines further down, which is exactly why the rule is absolute rather than
       a matter of care.) */
    .brand-logo-container {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 56px;
      height: 30px;
      padding: 2px 3px;
      /* Theme-INVARIANT by design (tokens/theme.css) - the mark is a light-ground asset and a
         plate that followed the theme would erase it on dark chrome. */
      background: var(--brand-plate, #ffffff);
      border: 1px solid var(--brand-plate-border, rgba(27, 31, 36, 0.15));
      border-radius: var(--radius-sm, 4px);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
      cursor: pointer;
      flex-shrink: 0;
      box-sizing: border-box;
      font: inherit;
      color: inherit;
    }
    /* System focus ring, not a branded one - SKILL.md 2.7 keeps focus indicators matching the OS
       convention rather than inventing a web-native colour. */
    .brand-logo-container:focus-visible {
      outline: 2px solid Highlight;
      outline-offset: 2px;
    }
    .brand-logo-img {
      height: 26px;
      width: auto;
      max-width: 52px;
      object-fit: contain;
      display: block;
    }
    .day-state-pipeline {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      background: var(--surface-primary);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
    }
    .pipeline-step {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: calc(var(--radius-sm) - 1px);
      font-family: var(--font-mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .pipeline-step.active {
      color: var(--accent-primary, #4f8eff);
      background: var(--surface-elevated);
      border: 1px solid var(--accent-primary, #4f8eff);
      opacity: 1;
      font-weight: 700;
    }
    .pipeline-step.completed {
      color: var(--text-secondary);
      background: var(--surface-secondary);
      border: 1px solid var(--border-subtle);
      opacity: 0.85;
    }
    .pipeline-step.pending {
      color: var(--text-muted);
      background: transparent;
      border: 1px dashed var(--border-subtle);
      opacity: 0.40;
    }
    /* Mission-034 P401 - the briefing/curation pair doubles as navigation (SKILL.md 2.7 -
       an interactive element carries pointer). Gate/monitor/eod steps stay display-only. */
    .pipeline-step.clickable {
      cursor: pointer;
    }
    .pipeline-step.clickable:hover {
      opacity: 1;
      border-style: solid;
      border-color: var(--accent-primary, #4f8eff);
    }
    /* Tier 6 Haute-Couture vector mark for each step (16px) */
    .step-icon {
      width: 16px;
      height: 16px;
      display: block;
      flex-shrink: 0;
    }
    .pipeline-arrow {
      color: var(--text-muted);
      font-family: var(--font-mono);
      font-size: 10px;
      opacity: 0.45;
      user-select: none;
      padding: 0 1px;
    }


    /* ── Centre zone: escalation banner slot ────────────────────── */
    .escalation-slot {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 16px;
    }

    /* ── Right zone: indicators + window controls ───────────────── */
    .indicators {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 0 12px;
      font-family: var(--font-mono);
      font-size: 9px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--text-muted);
    }
    .indicator {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .indicator-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--text-muted);
    }
    .indicator-dot.ok {
      background: var(--status-success, #3fb950);
      animation: dot-pulse 2s ease-in-out 1;
    }

    @keyframes dot-pulse {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.4); opacity: 0.7; }
    }

    @media (prefers-reduced-motion: reduce) {
      .indicator-dot.ok { animation: none; }
    }

    .window-controls {
      display: flex;
      height: 100%;
    }
    .window-controls button {
      width: 44px;
      height: 100%;
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-family: var(--font-system);
      font-size: 12px;
      cursor: default;
    }
    .window-controls button:hover {
      background: var(--surface-elevated);
      color: var(--text-primary);
    }
    .window-controls button.close:hover {
      background: var(--status-danger);
      color: var(--text-inverse);
    }

    /* ── Company Logo ───────────────────────────────────────────── */
    .company-logo {
      display: flex;
      align-items: center;
      height: 100%;
      padding: 0 12px;
      cursor: help;
    }
    .company-logo svg {
      height: 24px;
      width: auto;
      border-radius: 4px;
    }

    /* ── Theme toggle button ────────────────────────────────────── */
    .theme-toggle {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 24px;
      margin: 0 4px;
      background: var(--surface-elevated);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      color: var(--text-secondary);
      font-size: 14px;
      cursor: default;
      flex-shrink: 0;
    }
    /* SKILL.md §2.7 — hover applies instantly, no transition. */
    .theme-toggle:hover {
      background: var(--accent-primary);
      color: var(--text-on-accent);
    }
  `;

  connectedCallback(): void {
    super.connectedCallback();
    this._unsubDay = dayState.subscribe((s) => { this.submode = s; });
    this._unsubTheme = onThemeChange((t) => { this.theme = t; });
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this._unsubDay?.();
    this._unsubTheme?.();
  }

  private async withCurrentWindow(action: 'minimize' | 'toggleMaximize' | 'close'): Promise<void> {
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      const win = getCurrentWindow();
      if (action === 'minimize') await win.minimize();
      else if (action === 'toggleMaximize') await win.toggleMaximize();
      else await win.close();
    } catch (err) {
      console.warn(`Window control '${action}' unavailable outside Tauri runtime:`, err);
    }
  }

  private _getStepStatus(mode: TodaySubmode): 'active' | 'completed' | 'pending' {
    const currentIdx = SUBMODES.indexOf(this.submode);
    const modeIdx = SUBMODES.indexOf(mode);
    if (modeIdx === currentIdx) return 'active';
    if (modeIdx < currentIdx) return 'completed';
    return 'pending';
  }

  /**
   * Mission-034 P401 — the pipeline is the Today navigation spine for the Curation Studio.
   * ONLY the briefing⇄curation pair is clickable: curation is a freely-enterable submode
   * station (ADRbe-260628152240 v1.3 low-minor convention), whereas the Gate is lock-scoped
   * (entered exclusively via selectedContext.acquireLock — a clickable Gate step would open a
   * dead Gate with no candidate, the S2-07 stranding class) and monitor/eod keep their
   * existing entry semantics untouched.
   */
  private _stepNavTarget(mode: TodaySubmode): TodaySubmode | null {
    if (mode === 'curation' && this.submode === 'briefing') return 'curation';
    if (mode === 'briefing' && this.submode === 'curation') return 'briefing';
    return null;
  }

  private _onStepClick(mode: TodaySubmode): void {
    const target = this._stepNavTarget(mode);
    if (!target) return;
    try {
      dayState.transition(target);
    } catch (err) {
      // Frozen pre-market or a race with another transition — surface, never crash the bar.
      console.warn('[top-status-bar] submode navigation rejected:', err);
    }
  }

  private _onLogoClick(e: Event): void {
    e.stopPropagation();
    this._aboutOpen = true;
  }

  private _onAboutClose(): void {
    this._aboutOpen = false;
  }

  render(): unknown {
    return html`
      <div class="drag-region" data-tauri-drag-region>
        <button class="brand-logo-container"
                type="button"
                @click=${this._onLogoClick}
                title="Infinix © 2026 Selective Gradient Capital. All Rights Reserved."
                aria-label="About Infinix — © 2026 Selective Gradient Capital. All Rights Reserved.">
          <img class="brand-logo-img"
               src="${INFINIX_BRAND_LOGO_DATA_URI}"
               alt="" />
        </button>

        <div class="day-state-pipeline" aria-label="Investment Day Sequence">
          ${SUBMODES.map((mode, idx) => {
            const status = this._getStepStatus(mode);
            const info = SUBMODE_DISPLAY[mode];
            const navTarget = this._stepNavTarget(mode);
            return html`
              ${idx > 0 ? html`<span class="pipeline-arrow">→</span>` : ''}
              <span
                class="pipeline-step ${status} ${navTarget ? 'clickable' : ''}"
                title=${navTarget
                  ? mode === 'curation'
                    ? 'Open the P401 Execution Proposal Curation Studio'
                    : 'Return to Briefing'
                  : `Day State: ${info.label}`}
                @click=${() => this._onStepClick(mode)}
              >
                <img class="step-icon" src=${info.icon} alt="" draggable="false" />
                <span class="step-label">${info.label}</span>
              </span>
            `;
          })}
        </div>
      </div>


      <div class="escalation-slot">
        <!-- T500 breach / recon freeze banner mounts here at v0.2 -->
      </div>

      <div class="indicators">
        <span class="indicator">
          <span class="indicator-dot ok"></span>
          Market
        </span>
        <span class="indicator">
          <span class="indicator-dot ok"></span>
          Broker
        </span>
        <span class="indicator">
          <span class="indicator-dot"></span>
          Recon
        </span>
      </div>

      <button
        class="theme-toggle"
        @click=${() => toggleTheme()}
        title=${this.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        aria-label=${this.theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
      >${this.theme === 'dark' ? '☀️' : '🌙'}</button>

      <div class="company-logo"
           title="Infinix © 2026 Selective Gradient Capital. All Rights Reserved."
           aria-label="Infinix © 2026 Selective Gradient Capital. All Rights Reserved.">
        <svg viewBox="0 0 210 180" xmlns="http://www.w3.org/2000/svg">
          <title>Infinix © 2026 Selective Gradient Capital. All Rights Reserved.</title>
          <rect width="210" height="180" fill="#ffffff"/>
          <g transform="translate(105, 110)">
            <text x="0" y="0" font-family="'Segoe UI', Arial, sans-serif" font-size="80" font-weight="900" fill="#003b70" letter-spacing="-2" text-anchor="middle">
              SG<tspan fill="#D4A843">C</tspan>
            </text>
            <rect x="-70" y="15" width="140" height="18" fill="#8B6B99" rx="0"/>
          </g>
        </svg>
      </div>

      <div class="window-controls">
        <button @click=${() => this.withCurrentWindow('minimize')}
                title="Minimize" aria-label="Minimize">─</button>
        <button @click=${() => this.withCurrentWindow('toggleMaximize')}
                title="Maximize" aria-label="Maximize">▢</button>
        <button class="close"
                @click=${() => this.withCurrentWindow('close')}
                title="Close" aria-label="Close">✕</button>
      </div>

      <sgc-about-splash-modal
        .open=${this._aboutOpen}
        @close=${this._onAboutClose}
      ></sgc-about-splash-modal>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sgc-top-status-bar': SgcTopStatusBar;
  }
}
