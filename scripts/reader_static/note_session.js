// One note being edited in the reader's notes panel (task 4 M4): its text, the disk version
// that text is based on, and its saving. No DOM here: the panel (notes.js) shows a session,
// and later views (preview, a visual editor) will show the same session, so saving, conflicts
// and recovery work the same in every mode. The .md file is the only authority.
//
// Rules (ROADMAP task 4 M4):
// - "Saved" only after the server confirms the very text on screen (`rev`): an answer for an
//   older revision never marks newer text as saved.
// - One save at a time per note; text typed meanwhile is saved next.
// - A save names the version it's based on: the server writes only if the file still has it
//   (409 otherwise: a conflict, nothing written). Nothing here ever overwrites silently.
// - A failed save keeps the text and is retried; the server's absence is "offline".
// - A recovery draft (browser storage on this PC) is kept from the first edit until the
//   server confirms the latest revision, or the user discards it.
(() => {
  "use strict";
  const AUTOSAVE = 1500;  // ms after the last edit (decision D6)
  const RETRY = [2000, 5000, 10000, 30000];  // after a failed save, then every 30 s
  const TIMEOUT = 15000;  // a save without an answer by then has failed
  const DRAFT_WRITE = 300;  // ms: drafts follow the typing closely, without one write per key
  const DRAFT_DAYS = 30;
  const DRAFT_PREFIX = "myLibrary.draft.";
  // M7.1 S1a: "this exact draft is dealt with" (restored and saved elsewhere, or discarded),
  // for a draft kept under a document that left the library: <prefix><draft's storage key> ->
  // {raw: the draft's stored string then, time}. Never a deletion: another tab may write a
  // newer draft under the same key at any moment, and localStorage has no compare-and-delete;
  // a newer draft doesn't match the marker, so it is offered again
  const SETTLED_PREFIX = "myLibrary.settled.";
  // The library's key (libraries.scope: its id and folder), from the server: drafts are kept
  // under it, so a copy of this library (the same document ids) or another library served on
  // this port later never sees them. Drafts from before there was a key are shown only in the
  // default library (MYLIBRARY_LEGACY_DRAFTS), the only one there was then.
  const SCOPE = String(window.MYLIBRARY_SCOPE || "none");
  const LEGACY = window.MYLIBRARY_LEGACY_DRAFTS === true;

  // --- requests ---------------------------------------------------------------------------

  // {status, data}; a request that never got an answer throws, with .offline (unreachable)
  // or .timeout (no answer in time)
  async function request(token, path, body, { timeout = TIMEOUT, keepalive = false } = {}) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), timeout);
    let response;
    try {
      response = await fetch(path, {
        method: "POST",
        keepalive,
        signal: abort.signal,
        headers: { "Content-Type": "application/json", "X-Library-Token": token },
        body: JSON.stringify(body),
      });
    } catch {
      const timedOut = abort.signal.aborted;
      const error = new Error(timedOut ? "the server didn't answer in time"
        : "the server can't be reached");
      error.offline = !timedOut;
      error.timeout = timedOut;
      throw error;
    } finally {
      clearTimeout(timer);
    }
    let data = {};
    try {
      data = await response.json();
    } catch {
      data = {};
    }
    return { status: response.status, data };
  }

  // --- recovery drafts (browser storage on this PC) ----------------------------------------
  // One per tab and note: "myLibrary.draft.<library key>:<document id>|<note key>|<tab id>"
  // (before library keys: "myLibrary.draft.<document id>|<note key>|<tab id>"). A reload keeps
  // the tab id (sessionStorage), so a tab finds its own draft again. Storage may be refused
  // (private window, blocked, full): store() says so, and the panel shows it.

  const tabId = (() => {
    try {
      let id = sessionStorage.getItem("myLibrary.tab");
      if (!id) {
        id = Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem("myLibrary.tab", id);
      }
      return id;
    } catch {
      return Math.random().toString(36).slice(2, 10);
    }
  })();

  const drafts = {
    keyOf: (docId, noteKey, tab = tabId) =>
      `${DRAFT_PREFIX}${SCOPE}:${docId}|${noteKey}|${tab}`,
    store(docId, noteKey, draft) {
      try {
        localStorage.setItem(drafts.keyOf(docId, noteKey), JSON.stringify(draft));
        return true;
      } catch {
        return false;  // quota exceeded or storage blocked: no crash recovery for this text
      }
    },
    remove(storageKey) {
      try {
        localStorage.removeItem(storageKey);
      } catch {
        // nothing stored, or storage unavailable: nothing to remove
      }
    },
    // This note's drafts (any tab), newest first: [{storageKey, draft}]
    find(docId, noteKey) {
      const found = [];
      try {
        const prefixes = [`${DRAFT_PREFIX}${SCOPE}:${docId}|${noteKey}|`];
        if (LEGACY) prefixes.push(`${DRAFT_PREFIX}${docId}|${noteKey}|`);
        for (let i = 0; i < localStorage.length; i++) {
          const storageKey = localStorage.key(i);
          if (!prefixes.some((prefix) => storageKey?.startsWith(prefix))) continue;
          try {
            const draft = JSON.parse(localStorage.getItem(storageKey));
            if (typeof draft?.text === "string") found.push({ storageKey, draft });
          } catch {
            drafts.remove(storageKey);  // unreadable: not a draft any more
          }
        }
      } catch {
        return [];
      }
      return found.sort((a, b) => (b.draft.time || 0) - (a.draft.time || 0));
    },
    // A draft's stored string as it is now (null: none, or storage unavailable)
    read(storageKey) {
      try {
        return localStorage.getItem(storageKey);
      } catch {
        return null;
      }
    },
    // Mark the draft `raw` (its stored string) under `storageKey` as dealt with: one write, so
    // nothing another tab writes there meanwhile can be lost. False if storage refused it
    // (then the draft simply stays offered)
    settle(storageKey, raw) {
      try {
        localStorage.setItem(`${SETTLED_PREFIX}${storageKey}`,
          JSON.stringify({ raw, time: Date.now() }));
        return true;
      } catch {
        return false;
      }
    },
    settled(storageKey, raw) {
      try {
        return JSON.parse(localStorage.getItem(`${SETTLED_PREFIX}${storageKey}`))?.raw === raw;
      } catch {
        return false;
      }
    },
    // Drafts of this library kept under another document's id than `docId` (M7.1 S1a: a
    // document merged into another or removed while its note was being edited), newest
    // first, leaving out those dealt with (settle): [{storageKey, raw, docId, key, draft}].
    // Never moved, renamed or deleted here: each stays under its own document and note
    elsewhere(docId) {
      const found = [];
      const prefix = `${DRAFT_PREFIX}${SCOPE}:`;
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const storageKey = localStorage.key(i);
          if (!storageKey?.startsWith(prefix)) continue;
          const rest = storageKey.slice(prefix.length);
          const first = rest.indexOf("|");
          const last = rest.lastIndexOf("|");
          if (first < 0 || last <= first) continue;
          const owner = rest.slice(0, first);
          if (owner === docId) continue;
          try {
            const raw = localStorage.getItem(storageKey);
            const draft = JSON.parse(raw);
            if (typeof draft?.text === "string" && !drafts.settled(storageKey, raw)) {
              found.push({ storageKey, raw, docId: owner, key: rest.slice(first + 1, last), draft });
            }
          } catch {
            // unreadable: left for find() under its own document to deal with
          }
        }
      } catch {
        return [];
      }
      return found.sort((a, b) => (b.draft.time || 0) - (a.draft.time || 0));
    },
    // Drafts older than 30 days go (decision D1)
    expire(now = Date.now()) {
      try {
        const old = [];
        for (let i = 0; i < localStorage.length; i++) {
          const storageKey = localStorage.key(i);
          if (!storageKey?.startsWith(DRAFT_PREFIX)) continue;
          let time = 0;
          try {
            time = JSON.parse(localStorage.getItem(storageKey))?.time || 0;
          } catch {
            time = 0;
          }
          if (now - time > DRAFT_DAYS * 86400000) old.push(storageKey);
        }
        // Markers whose draft is gone, changed or old (removing one only shows a draft again)
        for (let i = 0; i < localStorage.length; i++) {
          const storageKey = localStorage.key(i);
          if (!storageKey?.startsWith(SETTLED_PREFIX)) continue;
          let marker = null;
          try {
            marker = JSON.parse(localStorage.getItem(storageKey));
          } catch {
            marker = null;
          }
          const draft = localStorage.getItem(storageKey.slice(SETTLED_PREFIX.length));
          if (draft === null || draft !== marker?.raw
            || now - (marker?.time || 0) > DRAFT_DAYS * 86400000) old.push(storageKey);
        }
        old.forEach(drafts.remove);
      } catch {
        // storage unavailable: nothing to expire
      }
    },
  };

  // --- a note session -----------------------------------------------------------------------

  class NoteSession {
    constructor({ token, docId, key, onChange = () => {}, onSaved = () => {},
      onHandoff = () => {} }) {
      Object.assign(this, { token, docId, key, onChange, onSaved, onHandoff });
      this.loaded = false;
      this.exists = false;
      this.base = null;  // the disk version `saved` came from (null: no file yet)
      this.saved = "";  // the text the server last confirmed (or loaded)
      this.text = "";  // the editor's text now
      this.rev = 0;  // revision of `text`: +1 per edit
      this.savedRev = 0;  // the revision `saved` is
      this.inFlight = null;  // {text, rev, base, promise}: the save on its way
      this.failure = null;  // {kind: "failed" | "offline", message}
      this.failures = 0;
      this.conflict = null;  // {text, version, exists}: the note on disk, not ours
      this.recovered = null;  // {storageKey, draft}: a draft found, waiting for Restore/Discard
      // {storageKey, raw, text}: another document's draft restored here (adoptDraft), bound
      // to the exact stored string it was restored from. Settled only when the server
      // confirms a save of exactly `text`; anything else (edited first, replaced, the disk
      // version chosen, a failure) leaves the original offered
      this.handoff = null;
      this.draftState = "none";  // "kept" | "failed" | "none"
      this.composing = false;  // IME composition in progress (Chinese input)
      this.timer = null;  // autosave
      this.retryTimer = null;
      this.draftTimer = null;
      this.checking = false;
      this.notice = "";  // a one-off message for the panel ("updated from disk")
    }

    // clean · dirty · saving · failed · offline · restarted · conflict · draft (to restore)
    get state() {
      if (this.conflict) return "conflict";
      if (this.recovered) return "draft";
      if (this.inFlight) return "saving";
      if (this.failure) return this.failure.kind;
      return this.text === this.saved ? "clean" : "dirty";
    }

    // Something the user could lose by closing the tab now (a recovery draft found but not
    // chosen yet stays in storage either way)
    get unconfirmed() {
      return this.text !== this.saved || this.inFlight !== null || this.conflict !== null;
    }

    changed() {
      this.onChange(this);
    }

    // The note as read from the server (/api/notes/get). Any drafts that differ from it are
    // offered; drafts equal to it are spent
    load(note) {
      this.base = note.version;
      this.saved = note.text;
      this.text = note.text;
      this.exists = note.exists;
      this.rev = this.savedRev = 0;
      this.failure = null;
      this.conflict = null;
      this.loaded = true;
      this.recovered = null;
      this.handoff = null;  // (a restore not confirmed: its original draft stays where it was)
      for (const found of drafts.find(this.docId, this.key)) {
        if (found.draft.text === note.text) drafts.remove(found.storageKey);
        else if (!this.recovered) this.recovered = found;
      }
      this.changed();
    }

    edit(text) {
      if (text === this.text) return;
      this.text = text;
      this.rev += 1;
      this.queueDraft();
      this.scheduleSave();
      this.changed();
    }

    setComposing(composing) {
      this.composing = composing;
      if (!composing) this.scheduleSave();  // the word is complete: save it in a moment
    }

    scheduleSave(delay = AUTOSAVE) {
      clearTimeout(this.timer);
      this.timer = null;
      // Paused: during a conflict or an offered draft (the user decides), and mid-composition;
      // after a failure the retry timer saves the latest text
      if (this.conflict || this.recovered || this.composing || this.failure) return;
      if (this.text === this.saved) return;
      this.timer = setTimeout(() => this.save(), delay);
    }

    // Send the text as it is now, unless a save is already on its way (then the next one
    // follows it). Resolves when this attempt has an answer
    save() {
      clearTimeout(this.timer);
      this.timer = null;
      if (!this.loaded || this.conflict || this.recovered) return Promise.resolve(this.state);
      if (this.inFlight) return this.inFlight.promise;
      if (this.text === this.saved) {  // nothing new to send (e.g. typed, then undone)
        this.cleared();
        this.changed();
        return Promise.resolve(this.state);
      }
      clearTimeout(this.retryTimer);
      const sent = { text: this.text, rev: this.rev, base: this.base };
      this.inFlight = sent;
      sent.promise = this.send(sent);
      this.changed();
      return sent.promise;
    }

    async send(sent) {
      let reply;
      try {
        reply = await request(this.token, "/api/notes/save",
          { id: this.docId, key: this.key, text: sent.text, base: sent.base });
      } catch (error) {
        this.inFlight = null;
        this.failed(error.offline ? "offline" : "failed", error.message);
        return this.state;
      }
      this.inFlight = null;
      if (reply.status === 200) {
        this.confirmed(sent, reply.data.version);
      } else if (reply.status === 409) {
        this.conflicted(reply.data.current);
      } else if (reply.status === 403) {
        // The server was started again since this page was opened: its access token is new,
        // so only a reload of the page can save. Not retried; the draft keeps the text
        this.queueDraft(true);
        this.failed("restarted", "the server was restarted: reload this page to go on saving",
          { retry: false });
      } else if (reply.status === 410) {
        // This document was merged into another or removed (M7.1 S1a): saving it again can
        // only be refused. As after a restart: not retried, the draft keeps the text
        this.queueDraft(true);
        this.failed("restarted", reply.data.error
          || "this document was merged into another or removed: reload to go on",
          { retry: false, gone: true, into: reply.data.into || "" });
      } else {
        this.failed("failed", reply.data.error || `HTTP ${reply.status}`);
      }
      return this.state;
    }

    // The server wrote `sent`: that text is saved. Newer typing stays unsaved, with its draft
    confirmed(sent, version) {
      this.base = version;
      this.saved = sent.text;
      this.savedRev = sent.rev;
      this.exists = true;
      this.cleared();
      this.onSaved(this);
      if (this.handoff && sent.text === this.handoff.text) {
        // The restored snapshot itself is what the server wrote: only now is its original
        // (that exact stored string, never a newer draft written there since) dealt with
        const done = this.handoff;
        this.handoff = null;
        if (drafts.settle(done.storageKey, done.raw)) this.onHandoff(this, done);
      }
      if (this.rev !== sent.rev) this.scheduleSave();
      this.changed();
    }

    // Nothing left to send: the failure is over, and the draft is spent if it's the text on
    // screen that is saved
    cleared() {
      this.failure = null;
      this.failures = 0;
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
      if (this.text === this.saved) {
        clearTimeout(this.draftTimer);
        this.draftTimer = null;
        drafts.remove(drafts.keyOf(this.docId, this.key));
        this.draftState = "none";
      }
    }

    failed(kind, message, { retry = true, gone = false, into = "" } = {}) {
      // gone: the document left the library (410); into: the one that kept its work, if any
      this.failure = { kind, message, gone, into };
      this.failures += 1;
      this.queueDraft(true);  // a failed save: the draft holds the newest text from now on
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
      if (retry) {
        const delay = RETRY[Math.min(this.failures - 1, RETRY.length - 1)];
        this.retryTimer = setTimeout(() => this.save(), delay);
      }
      this.changed();
    }

    retryNow() {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
      return this.save();  // the failure shows until this answer
    }

    conflicted(current) {
      clearTimeout(this.timer);
      clearTimeout(this.retryTimer);
      this.timer = this.retryTimer = null;
      this.failure = null;
      this.conflict = {
        text: current?.text ?? "",
        version: current?.version ?? null,
        exists: current?.exists ?? false,
      };
      this.queueDraft(true);  // the local text is kept, as a draft too
      this.changed();
    }

    // Save until the text on screen is confirmed, or a failure or conflict stops it
    // (switching notes, Save, Ctrl+S). Resolves with the state
    async flush() {
      for (let attempts = 0; attempts < 4; attempts++) {
        if (this.inFlight) {
          await this.inFlight.promise;
          continue;
        }
        if (this.conflict || this.recovered || this.text === this.saved) break;
        await this.save();
        if (this.failure) break;
      }
      return this.state;
    }

    // --- changes made elsewhere (VS Code, another tab) -------------------------------------

    // Is the file still at our version? While nothing is unsaved here, a changed file is
    // simply loaded; with unsaved text here, it's a conflict. Skipped while a save of ours is
    // on its way, and an answer older than our last save is ignored
    async checkDisk() {
      if (!this.loaded || this.inFlight || this.conflict || this.recovered || this.checking) {
        return;
      }
      const base = this.base;
      const rev = this.rev;
      this.checking = true;
      let reply;
      try {
        reply = await request(this.token, "/api/notes/version",
          { id: this.docId, key: this.key }, { timeout: 10000 });
      } catch {
        return;  // unreachable: a save will say so when there is one
      } finally {
        this.checking = false;
      }
      const stale = () => this.inFlight || this.base !== base || this.conflict || this.recovered;
      if (reply.status !== 200 || stale() || reply.data.version === this.base) return;
      let note;
      try {
        note = await request(this.token, "/api/notes/get", { id: this.docId, key: this.key });
      } catch {
        return;
      }
      if (note.status !== 200 || stale()) return;
      if (this.text === this.saved && this.rev === rev) {
        this.base = note.data.version;
        this.saved = this.text = note.data.text;
        this.exists = note.data.exists;
        this.rev += 1;
        this.savedRev = this.rev;
        this.notice = "updated";
        this.changed();
      } else {
        this.conflicted(note.data);
      }
    }

    // --- resolving a conflict ---------------------------------------------------------------

    // Keep mine: the server copies the disk version to archive/notes-conflicts/ and writes
    // this text, under the note's lock, only if the disk still has the version shown in the
    // conflict; if it changed again, that's a new conflict (nothing written)
    async keepMine() {
      if (!this.conflict) return { ok: false };
      const sent = { text: this.text, rev: this.rev, base: this.base };
      let reply;
      try {
        reply = await request(this.token, "/api/notes/save", {
          id: this.docId, key: this.key, text: sent.text, base: sent.base,
          overwrite: this.conflict.version,
        });
      } catch (error) {
        return { ok: false, message: error.message };
      }
      if (reply.status === 409) {
        this.conflicted(reply.data.current);
        return { ok: false, again: true };
      }
      if (reply.status !== 200) return { ok: false, message: reply.data.error || `HTTP ${reply.status}` };
      this.conflict = null;
      this.confirmed(sent, reply.data.version);
      return { ok: true, kept: reply.data.kept };
    }

    // Use the disk version: this text is first kept in archive/notes-conflicts/ (…mine.md); if
    // that fails, nothing is discarded. Then the note as it is on disk now is loaded
    async useDisk() {
      if (!this.conflict) return { ok: false };
      let kept;
      try {
        kept = await request(this.token, "/api/notes/keep-copy",
          { id: this.docId, key: this.key, text: this.text });
      } catch (error) {
        return { ok: false, message: error.message };
      }
      if (kept.status !== 200) return { ok: false, message: kept.data.error || `HTTP ${kept.status}` };
      let note;
      try {
        note = await request(this.token, "/api/notes/get", { id: this.docId, key: this.key });
      } catch (error) {
        return { ok: false, message: error.message, kept: kept.data.kept };
      }
      if (note.status !== 200) {
        return { ok: false, message: note.data.error || `HTTP ${note.status}`, kept: kept.data.kept };
      }
      this.conflict = null;
      this.handoff = null;  // (the disk version chosen: a restored draft's original stays)
      this.base = note.data.version;
      this.saved = this.text = note.data.text;
      this.exists = note.data.exists;
      this.rev += 1;
      this.savedRev = this.rev;
      this.cleared();
      this.changed();
      return { ok: true, kept: kept.data.kept };
    }

    // --- a recovery draft -------------------------------------------------------------------

    // Restore: the draft's text comes back. If the file is still the version the draft was
    // based on, it's simply unsaved text (saved in a moment); if the file changed since, it's a
    // conflict to resolve first
    async restoreDraft() {
      const found = this.recovered;
      if (!found) return { ok: false };
      let note;
      try {
        note = await request(this.token, "/api/notes/get", { id: this.docId, key: this.key });
      } catch (error) {
        return { ok: false, message: error.message };
      }
      if (note.status !== 200) return { ok: false, message: note.data.error || `HTTP ${note.status}` };
      this.recovered = null;
      drafts.remove(found.storageKey);  // it becomes this tab's draft
      const disk = note.data;
      this.exists = disk.exists;
      this.text = found.draft.text;
      this.rev += 1;
      if (found.draft.base === disk.version) {
        this.base = disk.version;
        this.saved = disk.text;
        this.queueDraft(true);
        this.scheduleSave();
        this.changed();
        return { ok: true };
      }
      this.base = found.draft.base ?? null;
      this.saved = disk.text;
      this.conflicted(disk);
      return { ok: true, conflict: true };
    }

    // M7.1 S1a: a draft kept under a document that left the library (merged into this one),
    // restored into this note, which the user chose. Only into a note with nothing of its own
    // waiting (no unsaved text, conflict, failure, draft of its own): nothing here is ever
    // written over. Bound to the draft exactly as offered (`found.raw`): if another tab wrote
    // there since, nothing is restored (look again). Then as restoreDraft: the same version
    // is saved at once; another is a conflict the user resolves. The original stays offered
    // until the server confirms a save of exactly the restored text
    async adoptDraft(found) {
      const occupied = () => !this.loaded || this.unconfirmed || this.recovered || this.failure
        || this.handoff || drafts.find(this.docId, this.key).length > 0;
      if (occupied()) return { ok: false, occupied: true };
      const raw = drafts.read(found.storageKey);
      let snapshot = null;
      try {
        snapshot = raw === found.raw ? JSON.parse(raw) : null;
      } catch {
        snapshot = null;
      }
      if (typeof snapshot?.text !== "string") return { ok: false, changed: true };
      let note;
      try {
        note = await request(this.token, "/api/notes/get", { id: this.docId, key: this.key });
      } catch (error) {
        return { ok: false, message: error.message };
      }
      if (note.status !== 200) return { ok: false, message: note.data.error || `HTTP ${note.status}` };
      if (occupied()) return { ok: false, occupied: true };  // (typed into meanwhile)
      const disk = note.data;
      if (snapshot.text === disk.text) {  // already there: that snapshot is dealt with
        const settled = drafts.settle(found.storageKey, raw);
        if (settled) this.onHandoff(this, found);
        return { ok: true, same: true, settled };
      }
      this.exists = disk.exists;
      this.text = snapshot.text;
      this.rev += 1;
      this.handoff = { storageKey: found.storageKey, raw, text: snapshot.text };
      this.saved = disk.text;
      if (snapshot.base === disk.version) {
        this.base = disk.version;
        this.queueDraft(true);
        this.changed();
        this.save();  // (at once: the snapshot itself, before anything is typed over it)
        return { ok: true };
      }
      // (its own base, not the disk's: "Keep mine" then keeps the note's text in
      // archive/notes-conflicts/ before writing, as for any conflict)
      this.base = snapshot.base ?? null;
      this.conflicted(disk);
      return { ok: true, conflict: true };
    }

    discardDraft() {
      if (!this.recovered) return;
      drafts.remove(this.recovered.storageKey);
      this.recovered = null;
      this.changed();
    }

    queueDraft(now = false) {
      if (now) {
        clearTimeout(this.draftTimer);
        this.draftTimer = null;
        this.writeDraft();
      } else if (!this.draftTimer) {
        this.draftTimer = setTimeout(() => this.writeDraft(), DRAFT_WRITE);
      }
    }

    writeDraft() {
      this.draftTimer = null;
      if (this.text === this.saved && !this.conflict) return;
      const ok = drafts.store(this.docId, this.key,
        { text: this.text, base: this.base, rev: this.rev, time: Date.now() });
      const state = ok ? "kept" : "failed";
      if (state !== this.draftState) {
        this.draftState = state;
        this.changed();
      }
    }

    // Leaving the page: the draft written now, and a last save sent (best effort: a small
    // note only, the browser keeps such requests short; never trusted alone)
    leaving() {
      if (this.draftTimer) this.queueDraft(true);
      if (this.inFlight || this.conflict || this.recovered || this.text === this.saved) return;
      if (new Blob([this.text]).size > 60000) return;
      request(this.token, "/api/notes/save",
        { id: this.docId, key: this.key, text: this.text, base: this.base },
        { keepalive: true }).catch(() => {});
    }
  }

  window.myLibraryNoteSession = Object.freeze({ NoteSession, drafts, request, tabId });
})();
