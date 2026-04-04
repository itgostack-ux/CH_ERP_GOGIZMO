/**
 * Operations Hub — Central State & Event Bus
 *
 * Single source of truth for the Operations Hub application state.
 * All modules read from and write to this state object.
 */

export const OpsState = {
	// ── User & Access ───────────────────────────────────
	user: null,
	user_fullname: null,
	roles: [],
	company: null,
	companies: [],

	// ── Warehouse Context ────────────────────────────────
	warehouses: [],         // warehouses the user can access
	active_warehouse: null, // currently selected warehouse filter

	// ── Active Module ────────────────────────────────────
	active_module: "dashboard",

	// ── Network ──────────────────────────────────────────
	is_online: navigator.onLine,

	// ── Dashboard Stats (cached) ─────────────────────────
	stats: {},

	/** Reset filters when switching modules */
	reset_filters() {
		this.active_warehouse = null;
		EventBus.emit("state:filters_reset");
	},
};

/**
 * Lightweight publish/subscribe event bus.
 */
export const EventBus = {
	_handlers: {},

	on(event, handler) {
		if (!this._handlers[event]) {
			this._handlers[event] = [];
		}
		this._handlers[event].push(handler);
	},

	off(event, handler) {
		if (!this._handlers[event]) return;
		if (handler) {
			this._handlers[event] = this._handlers[event].filter((h) => h !== handler);
		} else {
			delete this._handlers[event];
		}
	},

	emit(event, data) {
		const handlers = this._handlers[event];
		if (!handlers) return;
		for (const handler of handlers) {
			try {
				handler(data);
			} catch (e) {
				console.error(`[OpsHub EventBus] Error in handler for "${event}":`, e);
			}
		}
	},

	clear() {
		this._handlers = {};
	},
};
