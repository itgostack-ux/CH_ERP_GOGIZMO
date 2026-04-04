/**
 * Operations Hub — Layout Manager
 *
 * Orchestrates the app shell: header bar, sidebar, content panel.
 * Two-column layout (sidebar + content). No cart panel.
 */
import { OpsState, EventBus } from "../state.js";
import { Sidebar } from "./sidebar.js";
import { HeaderBar } from "./header_bar.js";

export class LayoutManager {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.sidebar = null;
		this.header_bar = null;

		this.$container = null;
		this.$content_panel = null;
	}

	init() {
		this._apply_fullscreen();
		this._render_shell();
		this._init_components();
		this._bind_module_switch();
	}

	_apply_fullscreen() {
		this.page.clear_actions();
		this.wrapper.find(".page-content").addClass("ops-hub-page");
		this.wrapper.find(".page-head").hide();
		$("header.navbar").hide();
		$("body").addClass("ops-hub-fullscreen");
		$(".main-section").css({ margin: 0, padding: 0, "max-width": "100%" });
		$(".page-container").css({ margin: 0, padding: 0, "max-width": "100%" });
	}

	_render_shell() {
		const content = this.wrapper.find(".layout-main-section");
		content.empty().append(`
			<div class="ops-hub-header-bar"></div>
			<div class="ops-hub-container">
				<div class="ops-hub-sidebar"></div>
				<div class="ops-hub-content-panel"></div>
			</div>
		`);

		this.$header_bar = content.find(".ops-hub-header-bar");
		this.$container = content.find(".ops-hub-container");
		this.$sidebar = content.find(".ops-hub-sidebar");
		this.$content_panel = content.find(".ops-hub-content-panel");
	}

	_init_components() {
		this.header_bar = new HeaderBar(this.$header_bar);
		this.sidebar = new Sidebar(this.$sidebar);
	}

	_bind_module_switch() {
		EventBus.on("module:switch", (module) => {
			this._switch_to(module);
		});
	}

	_switch_to(module) {
		this.$content_panel.off();
		this.$content_panel.empty();

		EventBus.emit("workspace:render", {
			module: module,
			panel: this.$content_panel,
		});
	}

	get content_panel() {
		return this.$content_panel;
	}

	destroy() {
		$("body").removeClass("ops-hub-fullscreen");
		$("header.navbar").show();
		EventBus.clear();
	}
}
