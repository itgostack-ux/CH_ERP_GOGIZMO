(()=>{var a={user:null,user_fullname:null,roles:[],company:null,companies:[],warehouses:[],active_warehouse:null,active_module:"dashboard",is_online:navigator.onLine,stats:{},reset_filters(){this.active_warehouse=null,o.emit("state:filters_reset")}},o={_handlers:{},on(r,e){this._handlers[r]||(this._handlers[r]=[]),this._handlers[r].push(e)},off(r,e){!this._handlers[r]||(e?this._handlers[r]=this._handlers[r].filter(s=>s!==e):delete this._handlers[r])},emit(r,e){let s=this._handlers[r];if(!!s)for(let t of s)try{t(e)}catch(i){console.error(`[OpsHub EventBus] Error in handler for "${r}":`,i)}},clear(){this._handlers={}}};var q={"Stock Manager":["dashboard","requests","transfers","receiving","reports"],"System Manager":["dashboard","requests","transfers","receiving","reports"],"Stock User":["dashboard","requests","transfers","receiving"],"Purchase User":["dashboard","requests"],"Purchase Manager":["dashboard","requests","reports"]},S=[{label:__("Overview"),modules:[{key:"dashboard",icon:"fa-tachometer",label:__("Dashboard")}]},{label:__("Procurement"),modules:[{key:"requests",icon:"fa-clipboard",label:__("Material Requests")}]},{label:__("Stock"),modules:[{key:"transfers",icon:"fa-truck",label:__("Transfers")},{key:"receiving",icon:"fa-download",label:__("Receiving")}]},{label:__("Insights"),modules:[{key:"reports",icon:"fa-bar-chart",label:__("Reports")}]}],c=class{constructor(e){this.wrapper=e,this.collapsed=localStorage.getItem("ops_hub_sidebar_collapsed")==="1",this._allowed_modules=null,this.render(),this._bind(),this._auto_responsive(),this.collapsed&&this._apply_collapsed(!0)}_auto_responsive(){if(!window.matchMedia)return;let e=window.matchMedia("(max-width: 1024px)"),s=t=>{t.matches&&!this.collapsed?(this.collapsed=!0,this._apply_collapsed(!0)):!t.matches&&this.collapsed&&localStorage.getItem("ops_hub_sidebar_collapsed")!=="1"&&(this.collapsed=!1,this._apply_collapsed(!1))};e.addEventListener("change",s),e.matches&&!this.collapsed&&(this.collapsed=!0,this._apply_collapsed(!0))}_compute_allowed_modules(){let e=a.roles||[];if(!e.length){this._allowed_modules=null;return}let s=new Set;for(let t of e){let i=q[t];i&&i.forEach(l=>s.add(l))}this._allowed_modules=s.size?s:null}_is_module_allowed(e){return this._allowed_modules?this._allowed_modules.has(e):!0}render(){this._compute_allowed_modules();let e=`
			<button class="ops-sidebar-toggle" title="${__("Toggle sidebar")}">
				<i class="fa fa-chevron-left"></i>
			</button>`;for(let l of S){let n=l.modules.filter(p=>this._is_module_allowed(p.key));if(!!n.length){e+=`<div class="ops-sidebar-section">${l.label}</div>`;for(let p of n)e+=`
					<button class="ops-sidebar-item${p.key===a.active_module?" active":""}"
						data-module="${p.key}"
						title="${p.label}">
						<span class="sidebar-icon"><i class="fa ${p.icon}"></i></span>
						<span class="sidebar-label">${p.label}</span>
					</button>`}}let s=a.user_fullname||frappe.session.user_fullname||"User",t=s.split(" ").map(l=>l[0]).join("").substring(0,2).toUpperCase(),i=a.company||"";e+=`
			<div class="ops-sidebar-bottom">
				<div class="ops-sidebar-identity">
					<div class="ops-sidebar-avatar">${frappe.utils.escape_html(t)}</div>
					<div class="ops-sidebar-detail">
						<span class="ops-sidebar-name">${frappe.utils.escape_html(s)}</span>
						<span class="ops-sidebar-company">${frappe.utils.escape_html(i)}</span>
					</div>
				</div>
				<div class="ops-sidebar-status">
					<span class="ops-online-dot${navigator.onLine?"":" offline"}"></span>
					<span class="ops-online-label">${navigator.onLine?__("Online"):__("Offline")}</span>
				</div>
			</div>`,this.wrapper.html(e)}_bind(){let e=this.wrapper;e.on("click",".ops-sidebar-toggle",()=>{this.collapsed=!this.collapsed,localStorage.setItem("ops_hub_sidebar_collapsed",this.collapsed?"1":"0"),this._apply_collapsed(this.collapsed)}),e.on("click",".ops-sidebar-item",function(){let s=$(this).data("module");s!==a.active_module&&(e.find(".ops-sidebar-item").removeClass("active"),$(this).addClass("active"),a.active_module=s,o.emit("module:switch",s))}),o.on("module:set",s=>{e.find(".ops-sidebar-item").removeClass("active"),e.find(`.ops-sidebar-item[data-module="${s}"]`).addClass("active"),a.active_module=s}),o.on("context:loaded",()=>{this.render(),this.collapsed&&this._apply_collapsed(!0)})}_apply_collapsed(e){let s=this.wrapper.closest(".ops-hub-container");e?(this.wrapper.addClass("collapsed"),s.addClass("sidebar-collapsed"),this.wrapper.find(".ops-sidebar-toggle i").removeClass("fa-chevron-left").addClass("fa-chevron-right")):(this.wrapper.removeClass("collapsed"),s.removeClass("sidebar-collapsed"),this.wrapper.find(".ops-sidebar-toggle i").removeClass("fa-chevron-right").addClass("fa-chevron-left"))}};var d=class{constructor(e){this.wrapper=e,this.render(),this._bind()}render(){let e=a.user_fullname||frappe.session.user_fullname||frappe.session.user,s=a.company||"",i=(a.roles||[]).filter(l=>["Stock Manager","Stock User","Purchase User","Purchase Manager","System Manager"].includes(l))[0]||"User";this.wrapper.html(`
			<div class="ops-header-inner">
				<div class="ops-header-left">
					<span class="ops-header-title">
						<i class="fa fa-th-large"></i>
						${__("Operations Hub")}
					</span>
				</div>

				<div class="ops-header-center">
					<div class="ops-warehouse-selector" style="display:${a.warehouses.length>1?"block":"none"}">
						<select class="ops-warehouse-filter">
							<option value="">${__("All Warehouses")}</option>
						</select>
					</div>
				</div>

				<div class="ops-header-right">
					<span class="ops-header-company">${frappe.utils.escape_html(s)}</span>
					<span class="ops-header-divider">|</span>
					<span class="ops-header-role">${frappe.utils.escape_html(i)}</span>
					<span class="ops-header-divider">|</span>
					<span class="ops-header-user">${frappe.utils.escape_html(e)}</span>
					<span class="ops-online-dot${navigator.onLine?"":" offline"}"></span>
				</div>
			</div>
		`),this._populate_warehouses()}_populate_warehouses(){let e=this.wrapper.find(".ops-warehouse-filter");for(let s of a.warehouses)e.append(`<option value="${frappe.utils.escape_html(s)}">${frappe.utils.escape_html(s)}</option>`);a.active_warehouse&&e.val(a.active_warehouse)}_bind(){this.wrapper.on("change",".ops-warehouse-filter",e=>{a.active_warehouse=$(e.target).val()||null,o.emit("warehouse:changed",a.active_warehouse)}),window.addEventListener("online",()=>{this.wrapper.find(".ops-online-dot").removeClass("offline"),a.is_online=!0}),window.addEventListener("offline",()=>{this.wrapper.find(".ops-online-dot").addClass("offline"),a.is_online=!1}),o.on("context:loaded",()=>this.render())}};var _=class{constructor(e){this.wrapper=$(e),this.page=e.page,this.sidebar=null,this.header_bar=null,this.$container=null,this.$content_panel=null}init(){this._apply_fullscreen(),this._render_shell(),this._init_components(),this._bind_module_switch()}_apply_fullscreen(){this.page.clear_actions(),this.wrapper.find(".page-content").addClass("ops-hub-page"),this.wrapper.find(".page-head").hide(),$("header.navbar").hide(),$("body").addClass("ops-hub-fullscreen"),$(".main-section").css({margin:0,padding:0,"max-width":"100%"}),$(".page-container").css({margin:0,padding:0,"max-width":"100%"})}_render_shell(){let e=this.wrapper.find(".layout-main-section");e.empty().append(`
			<div class="ops-hub-header-bar"></div>
			<div class="ops-hub-container">
				<div class="ops-hub-sidebar"></div>
				<div class="ops-hub-content-panel"></div>
			</div>
		`),this.$header_bar=e.find(".ops-hub-header-bar"),this.$container=e.find(".ops-hub-container"),this.$sidebar=e.find(".ops-hub-sidebar"),this.$content_panel=e.find(".ops-hub-content-panel")}_init_components(){this.header_bar=new d(this.$header_bar),this.sidebar=new c(this.$sidebar)}_bind_module_switch(){o.on("module:switch",e=>{this._switch_to(e)})}_switch_to(e){this.$content_panel.off(),this.$content_panel.empty(),o.emit("workspace:render",{module:e,panel:this.$content_panel})}get content_panel(){return this.$content_panel}destroy(){$("body").removeClass("ops-hub-fullscreen"),$("header.navbar").show(),o.clear()}};var h=class{constructor(){this._panel=null,o.on("workspace:render",e=>{e.module==="dashboard"&&(this._panel=e.panel,this.render())})}render(){this._panel.html(`
			<div class="ops-module-panel ops-dashboard-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#eff6ff;color:#1d4ed8">
							<i class="fa fa-tachometer"></i>
						</span>
						${__("Operations Dashboard")}
					</h4>
					<span class="ops-module-hint">${__("Real-time overview of procurement, stock, and fulfillment")}</span>
				</div>

				<div class="ops-dashboard-kpis">
					<div class="ops-kpi-card" data-navigate="requests">
						<div class="ops-kpi-value" id="kpi-pending-requests">\u2014</div>
						<div class="ops-kpi-label">${__("Pending Requests")}</div>
						<div class="ops-kpi-sub" id="kpi-pending-approval">\u2014</div>
					</div>
					<div class="ops-kpi-card ops-kpi-danger" data-navigate="requests">
						<div class="ops-kpi-value" id="kpi-sla-breached">\u2014</div>
						<div class="ops-kpi-label">${__("SLA Breached")}</div>
						<div class="ops-kpi-sub">${__("Overdue requests")}</div>
					</div>
					<div class="ops-kpi-card" data-navigate="transfers">
						<div class="ops-kpi-value" id="kpi-active-transfers">\u2014</div>
						<div class="ops-kpi-label">${__("Active Transfers")}</div>
						<div class="ops-kpi-sub" id="kpi-in-transit">\u2014</div>
					</div>
					<div class="ops-kpi-card" data-navigate="receiving">
						<div class="ops-kpi-value" id="kpi-pending-receipt">\u2014</div>
						<div class="ops-kpi-label">${__("Pending Receipt")}</div>
						<div class="ops-kpi-sub">${__("Awaiting GRN")}</div>
					</div>
				</div>

				<div class="ops-dashboard-actions">
					<h5>${__("Quick Actions")}</h5>
					<div class="ops-action-grid">
						<button class="ops-action-btn" data-action="new_request">
							<i class="fa fa-plus-circle"></i> ${__("New Material Request")}
						</button>
						<button class="ops-action-btn" data-action="check_stock">
							<i class="fa fa-search"></i> ${__("Check Stock Availability")}
						</button>
						<button class="ops-action-btn" data-action="sla_report">
							<i class="fa fa-clock-o"></i> ${__("SLA Report")}
						</button>
						<button class="ops-action-btn" data-action="shortage_report">
							<i class="fa fa-exclamation-triangle"></i> ${__("Stock Shortage Report")}
						</button>
					</div>
				</div>

				<div class="ops-dashboard-recent">
					<h5>${__("Recent Activity")}</h5>
					<div class="ops-recent-list" id="ops-recent-activity">
						<div class="ops-loading-skeleton">
							<div class="skeleton-line"></div>
							<div class="skeleton-line short"></div>
							<div class="skeleton-line"></div>
						</div>
					</div>
				</div>
			</div>
		`),this._bind_actions(),this._load_stats()}_bind_actions(){this._panel.on("click",".ops-kpi-card[data-navigate]",function(){let e=$(this).data("navigate");o.emit("module:set",e),o.emit("module:switch",e)}),this._panel.on("click",".ops-action-btn",function(){let e=$(this).data("action");e==="new_request"?frappe.new_doc("Material Request",{material_request_type:"Material Transfer"}):e==="check_stock"?(o.emit("module:set","requests"),o.emit("module:switch","requests")):e==="sla_report"?frappe.set_route("query-report","Store Material Request SLA"):e==="shortage_report"&&frappe.set_route("query-report","Stock Shortage By Store")})}_load_stats(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_dashboard_stats",args:{warehouse:a.active_warehouse||""},callback:e=>{if(!e.message)return;let s=e.message;a.stats=s,this._panel.find("#kpi-pending-requests").text(s.pending_requests||0),this._panel.find("#kpi-pending-approval").text(__("{0} awaiting approval",[s.pending_approval||0])),this._panel.find("#kpi-sla-breached").text(s.sla_breached||0),this._panel.find("#kpi-active-transfers").text(s.active_transfers||0),this._panel.find("#kpi-in-transit").text(__("{0} in transit",[s.in_transit||0])),this._panel.find("#kpi-pending-receipt").text(s.pending_receipt||0),this._render_recent(s.recent_activity||[])}})}_render_recent(e){let s=this._panel.find("#ops-recent-activity");if(!e.length){s.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No recent activity")}</p>
			</div>`);return}let t="";for(let i of e){let l=i.type==="Material Request"?"fa-clipboard":i.type==="Stock Entry"?"fa-truck":"fa-file-text-o",n=frappe.datetime.prettyDate(i.creation);t+=`
				<div class="ops-recent-item" data-doctype="${frappe.utils.escape_html(i.type)}" data-name="${frappe.utils.escape_html(i.name)}">
					<span class="ops-recent-icon"><i class="fa ${l}"></i></span>
					<div class="ops-recent-detail">
						<span class="ops-recent-name">${frappe.utils.escape_html(i.name)}</span>
						<span class="ops-recent-desc">${frappe.utils.escape_html(i.description||"")}</span>
					</div>
					<span class="ops-recent-meta">
						<span class="ops-recent-status ops-status-${(i.status||"").toLowerCase().replace(/\s+/g,"-")}">${frappe.utils.escape_html(i.status||"")}</span>
						<span class="ops-recent-time">${n}</span>
					</span>
				</div>`}s.html(t),s.on("click",".ops-recent-item",function(){frappe.set_route("Form",$(this).data("doctype"),$(this).data("name"))})}};var g=[{key:"pending_approval",label:__("Pending Approval"),filter:{custom_approval_status:"Pending Approval",docstatus:0}},{key:"approved",label:__("Approved"),filter:{custom_approval_status:"Approved",docstatus:1,status:["not in",["Stopped","Cancelled","Received","Transferred"]]}},{key:"in_progress",label:__("In Progress"),filter:{docstatus:1,status:["in",["Ordered","Partially Ordered","Partially Received"]],custom_approval_status:"Approved"}},{key:"completed",label:__("Completed"),filter:{docstatus:1,status:["in",["Received","Transferred"]]}},{key:"all",label:__("All"),filter:{docstatus:["in",[0,1]]}}],R={Urgent:"#dc2626",Standard:"#2563eb",Low:"#6b7280"},u=class{constructor(){this._panel=null,this._active_tab="pending_approval",this._requests=[],o.on("workspace:render",e=>{e.module==="requests"&&(this._panel=e.panel,this.render())})}render(){let e=g.map(s=>`<button class="ops-tab${s.key===this._active_tab?" active":""}" data-tab="${s.key}">${s.label}
				<span class="ops-tab-count" id="tab-count-${s.key}"></span></button>`).join("");this._panel.html(`
			<div class="ops-module-panel ops-requests-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#fef3c7;color:#92400e">
							<i class="fa fa-clipboard"></i>
						</span>
						${__("Material Requests")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-primary btn-sm ops-new-request">
							<i class="fa fa-plus"></i> ${__("New Request")}
						</button>
						<button class="btn btn-default btn-sm ops-refresh-requests">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${e}</div>

				<div class="ops-request-filters">
					<select class="ops-filter-priority">
						<option value="">${__("All Priorities")}</option>
						<option value="Urgent">${__("Urgent")}</option>
						<option value="Standard">${__("Standard")}</option>
						<option value="Low">${__("Low")}</option>
					</select>
					<select class="ops-filter-store">
						<option value="">${__("All Stores")}</option>
					</select>
				</div>

				<div class="ops-request-list" id="ops-request-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
					</div>
				</div>
			</div>
		`),this._bind(),this._load_stores(),this._load_requests()}_bind(){this._panel.on("click",".ops-tab",e=>{let s=$(e.currentTarget).data("tab");this._active_tab=s,this._panel.find(".ops-tab").removeClass("active"),$(e.currentTarget).addClass("active"),this._load_requests()}),this._panel.on("click",".ops-new-request",()=>{frappe.new_doc("Material Request",{material_request_type:"Material Transfer"})}),this._panel.on("click",".ops-refresh-requests",()=>{this._load_requests()}),this._panel.on("change",".ops-filter-priority, .ops-filter-store",()=>{this._load_requests()}),this._panel.on("click",".ops-req-row",function(){frappe.set_route("Form","Material Request",$(this).data("name"))}),this._panel.on("click",".ops-btn-approve",e=>{e.stopPropagation(),this._approve_request($(e.currentTarget).data("name"))}),this._panel.on("click",".ops-btn-reject",e=>{e.stopPropagation(),this._reject_request($(e.currentTarget).data("name"))}),this._panel.on("click",".ops-btn-allocate",e=>{e.stopPropagation(),this._auto_allocate($(e.currentTarget).data("name"))}),o.on("warehouse:changed",()=>this._load_requests())}_load_stores(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_stores",callback:e=>{let s=e.message||[],t=this._panel.find(".ops-filter-store");for(let i of s)t.append(`<option value="${frappe.utils.escape_html(i.name)}">${frappe.utils.escape_html(i.store_name||i.name)}</option>`)}})}_load_requests(){let e=g.find(i=>i.key===this._active_tab),s=this._panel.find(".ops-filter-priority").val()||"",t=this._panel.find(".ops-filter-store").val()||"";frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_request_queue",args:{tab:this._active_tab,priority:s,store:t,warehouse:a.active_warehouse||""},callback:i=>{this._requests=i.message||[],this._render_list(),this._load_tab_counts()}})}_load_tab_counts(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_request_tab_counts",args:{warehouse:a.active_warehouse||""},callback:e=>{let s=e.message||{};for(let[t,i]of Object.entries(s))this._panel.find(`#tab-count-${t}`).text(i||"")}})}_render_list(){let e=this._panel.find("#ops-request-list");if(!this._requests.length){e.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No requests found")}</p>
			</div>`);return}let s="";for(let t of this._requests){let i=R[t.priority]||"#6b7280",l=t.sla_breached?"ops-sla-breached":"",n=t.sla_breached?`<span class="ops-sla-badge" title="${__("SLA Breached")}"><i class="fa fa-exclamation-circle"></i></span>`:"",p=frappe.datetime.prettyDate(t.creation),b=t.item_count||0,k=t.approval_status==="Pending Approval"?`<button class="btn btn-xs btn-success ops-btn-approve" data-name="${frappe.utils.escape_html(t.name)}">
					<i class="fa fa-check"></i> ${__("Approve")}
				   </button>
				   <button class="btn btn-xs btn-danger ops-btn-reject" data-name="${frappe.utils.escape_html(t.name)}">
					<i class="fa fa-times"></i> ${__("Reject")}
				   </button>`:"",y=t.approval_status==="Approved"&&t.status==="Pending"?`<button class="btn btn-xs btn-primary ops-btn-allocate" data-name="${frappe.utils.escape_html(t.name)}">
					<i class="fa fa-magic"></i> ${__("Allocate")}
				   </button>`:"",w=t.sla_due_by?`<span class="ops-req-sla ${l}">
					${n} ${__("Due")}: ${frappe.datetime.str_to_user(t.sla_due_by)}
				   </span>`:"";s+=`
				<div class="ops-req-row ${l}" data-name="${frappe.utils.escape_html(t.name)}">
					<div class="ops-req-priority" style="background:${i}"></div>
					<div class="ops-req-main">
						<div class="ops-req-top">
							<span class="ops-req-name">${frappe.utils.escape_html(t.name)}</span>
							<span class="ops-req-store">${frappe.utils.escape_html(t.store||"")}</span>
							<span class="ops-req-priority-label" style="color:${i}">${frappe.utils.escape_html(t.priority)}</span>
						</div>
						<div class="ops-req-bottom">
							<span class="ops-req-items">${b} ${__("items")}</span>
							<span class="ops-req-status ops-status-${(t.status||"").toLowerCase().replace(/\s+/g,"-")}">${frappe.utils.escape_html(t.status)}</span>
							${w}
							<span class="ops-req-time">${p}</span>
						</div>
					</div>
					<div class="ops-req-actions">
						${k}
						${y}
					</div>
				</div>`}e.html(s)}_approve_request(e){frappe.confirm(__("Approve Material Request {0}?",[e]),()=>{frappe.call({method:"ch_erp15.ch_erp15.store_request_api.approve_store_request",args:{request_name:e},callback:s=>{s.message&&(frappe.show_alert({message:__("Request {0} approved",[e]),indicator:"green"}),this._load_requests())}})})}_reject_request(e){let s=new frappe.ui.Dialog({title:__("Reject Request"),fields:[{label:__("Reason"),fieldname:"reason",fieldtype:"Small Text",reqd:1}],primary_action_label:__("Reject"),primary_action:t=>{s.hide(),frappe.call({method:"ch_erp15.ch_erp15.store_request_api.reject_store_request",args:{request_name:e,reason:t.reason},callback:i=>{i.message&&(frappe.show_alert({message:__("Request {0} rejected",[e]),indicator:"orange"}),this._load_requests())}})}});s.show()}_auto_allocate(e){frappe.call({method:"ch_erp15.ch_erp15.store_request_api.auto_allocate_sources",args:{request_name:e},freeze:!0,freeze_message:__("Checking stock availability..."),callback:s=>{s.message&&(frappe.show_alert({message:__("Allocation suggested for {0}",[e]),indicator:"green"}),frappe.set_route("Form","Material Request",e))}})}};var A=[{key:"draft",label:__("Draft"),filter:{docstatus:0}},{key:"in_transit",label:__("In Transit"),filter:{docstatus:1,custom_status:"In Transit"}},{key:"dispatched",label:__("Dispatched"),filter:{docstatus:1,custom_status:"Dispatched"}},{key:"completed",label:__("Completed"),filter:{docstatus:1,custom_status:["in",["Received","Completed",""]]}},{key:"all",label:__("All"),filter:{docstatus:["in",[0,1]]}}],f=class{constructor(){this._panel=null,this._active_tab="in_transit",this._transfers=[],o.on("workspace:render",e=>{e.module==="transfers"&&(this._panel=e.panel,this.render())})}render(){let e=A.map(s=>`<button class="ops-tab${s.key===this._active_tab?" active":""}" data-tab="${s.key}">${s.label}
				<span class="ops-tab-count" id="transfer-tab-${s.key}"></span></button>`).join("");this._panel.html(`
			<div class="ops-module-panel ops-transfers-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#ecfdf5;color:#059669">
							<i class="fa fa-truck"></i>
						</span>
						${__("Stock Transfers")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-primary btn-sm ops-new-transfer">
							<i class="fa fa-plus"></i> ${__("New Transfer")}
						</button>
						<button class="btn btn-default btn-sm ops-refresh-transfers">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${e}</div>

				<div class="ops-transfer-list" id="ops-transfer-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
					</div>
				</div>
			</div>
		`),this._bind(),this._load_transfers()}_bind(){this._panel.on("click",".ops-tab",e=>{let s=$(e.currentTarget).data("tab");this._active_tab=s,this._panel.find(".ops-tab").removeClass("active"),$(e.currentTarget).addClass("active"),this._load_transfers()}),this._panel.on("click",".ops-new-transfer",()=>{frappe.new_doc("Stock Entry",{stock_entry_type:"Material Transfer"})}),this._panel.on("click",".ops-refresh-transfers",()=>{this._load_transfers()}),this._panel.on("click",".ops-transfer-row",function(){frappe.set_route("Form","Stock Entry",$(this).data("name"))}),o.on("warehouse:changed",()=>this._load_transfers())}_load_transfers(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_transfer_queue",args:{tab:this._active_tab,warehouse:a.active_warehouse||""},callback:e=>{this._transfers=e.message||[],this._render_list()}})}_render_list(){let e=this._panel.find("#ops-transfer-list");if(!this._transfers.length){e.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${__("No transfers found")}</p>
			</div>`);return}let s="";for(let t of this._transfers){let i=(t.custom_status||t.docstatus_label||"").toLowerCase().replace(/\s+/g,"-"),l=frappe.datetime.prettyDate(t.creation),n=t.material_request?`<span class="ops-transfer-mr">${__("MR")}: ${frappe.utils.escape_html(t.material_request)}</span>`:"";s+=`
				<div class="ops-transfer-row" data-name="${frappe.utils.escape_html(t.name)}">
					<div class="ops-transfer-main">
						<div class="ops-transfer-top">
							<span class="ops-transfer-name">${frappe.utils.escape_html(t.name)}</span>
							<span class="ops-transfer-type">${frappe.utils.escape_html(t.stock_entry_type)}</span>
							${n}
						</div>
						<div class="ops-transfer-route">
							<span class="ops-wh-from">${frappe.utils.escape_html(t.from_warehouse||"\u2014")}</span>
							<i class="fa fa-long-arrow-right"></i>
							<span class="ops-wh-to">${frappe.utils.escape_html(t.to_warehouse||"\u2014")}</span>
						</div>
						<div class="ops-transfer-bottom">
							<span class="ops-transfer-items">${t.item_count||0} ${__("items")}</span>
							<span class="ops-transfer-status ops-status-${i}">${frappe.utils.escape_html(t.custom_status||(t.docstatus===0?"Draft":"Submitted"))}</span>
							<span class="ops-transfer-time">${l}</span>
						</div>
					</div>
				</div>`}e.html(s)}};var C=[{key:"pending",label:__("Pending Receipt")},{key:"received",label:__("Recently Received")}],m=class{constructor(){this._panel=null,this._active_tab="pending",this._items=[],o.on("workspace:render",e=>{e.module==="receiving"&&(this._panel=e.panel,this.render())})}render(){let e=C.map(s=>`<button class="ops-tab${s.key===this._active_tab?" active":""}" data-tab="${s.key}">${s.label}
				<span class="ops-tab-count" id="recv-tab-${s.key}"></span></button>`).join("");this._panel.html(`
			<div class="ops-module-panel ops-receiving-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#f0fdf4;color:#16a34a">
							<i class="fa fa-download"></i>
						</span>
						${__("Stock Receiving")}
					</h4>
					<div class="ops-module-actions">
						<button class="btn btn-default btn-sm ops-refresh-receiving">
							<i class="fa fa-refresh"></i>
						</button>
					</div>
				</div>

				<div class="ops-tab-bar">${e}</div>

				<div class="ops-receiving-list" id="ops-receiving-list">
					<div class="ops-loading-skeleton">
						<div class="skeleton-line"></div>
						<div class="skeleton-line short"></div>
						<div class="skeleton-line"></div>
					</div>
				</div>
			</div>
		`),this._bind(),this._load_items()}_bind(){this._panel.on("click",".ops-tab",e=>{let s=$(e.currentTarget).data("tab");this._active_tab=s,this._panel.find(".ops-tab").removeClass("active"),$(e.currentTarget).addClass("active"),this._load_items()}),this._panel.on("click",".ops-refresh-receiving",()=>{this._load_items()}),this._panel.on("click",".ops-recv-row",function(){let e=$(this).data("doctype"),s=$(this).data("name");frappe.set_route("Form",e,s)}),o.on("warehouse:changed",()=>this._load_items())}_load_items(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_receiving_queue",args:{tab:this._active_tab,warehouse:a.active_warehouse||""},callback:e=>{this._items=e.message||[],this._render_list()}})}_render_list(){let e=this._panel.find("#ops-receiving-list");if(!this._items.length){e.html(`<div class="ops-empty-state">
				<i class="fa fa-inbox"></i>
				<p>${this._active_tab==="pending"?__("No pending receipts"):__("No recent receipts")}</p>
			</div>`);return}let s="";for(let t of this._items){let i=t.doctype==="Purchase Receipt"?"fa-shopping-bag":"fa-truck",l=frappe.datetime.prettyDate(t.creation),n=t.from_warehouse?`<span class="ops-recv-from">${__("From")}: ${frappe.utils.escape_html(t.from_warehouse)}</span>`:t.supplier?`<span class="ops-recv-from">${__("Supplier")}: ${frappe.utils.escape_html(t.supplier)}</span>`:"";s+=`
				<div class="ops-recv-row" data-doctype="${frappe.utils.escape_html(t.doctype)}" data-name="${frappe.utils.escape_html(t.name)}">
					<span class="ops-recv-icon"><i class="fa ${i}"></i></span>
					<div class="ops-recv-main">
						<div class="ops-recv-top">
							<span class="ops-recv-name">${frappe.utils.escape_html(t.name)}</span>
							<span class="ops-recv-type">${frappe.utils.escape_html(t.doctype)}</span>
						</div>
						<div class="ops-recv-bottom">
							${n}
							<span class="ops-recv-to">${__("To")}: ${frappe.utils.escape_html(t.to_warehouse||"")}</span>
							<span class="ops-recv-items">${t.item_count||0} ${__("items")}</span>
							<span class="ops-recv-time">${l}</span>
						</div>
					</div>
				</div>`}e.html(s)}};var T=[{key:"sla",title:__("Material Request SLA"),description:__("Track SLA compliance for store material requests"),icon:"fa-clock-o",route:"query-report/Store Material Request SLA",color:"#4f46e5"},{key:"shortage",title:__("Stock Shortage by Store"),description:__("Identify stock gaps across stores"),icon:"fa-exclamation-triangle",route:"query-report/Stock Shortage By Store",color:"#dc2626"},{key:"transfer_sla",title:__("Transfer SLA Report"),description:__("Monitor transfer timelines and delays"),icon:"fa-truck",route:"query-report/Transfer SLA Report",color:"#059669"},{key:"purchase_receipt",title:__("Purchase Receipt Report"),description:__("Track purchase receipts and supplier delivery"),icon:"fa-shopping-bag",route:"query-report/Purchase Receipt Report",color:"#d97706"}],v=class{constructor(){this._panel=null,o.on("workspace:render",e=>{e.module==="reports"&&(this._panel=e.panel,this.render())})}render(){let e="";for(let s of T)e+=`
				<div class="ops-report-card" data-route="${s.route}">
					<div class="ops-report-icon" style="background:${s.color}15;color:${s.color}">
						<i class="fa ${s.icon}"></i>
					</div>
					<div class="ops-report-detail">
						<h6>${s.title}</h6>
						<p>${s.description}</p>
					</div>
					<i class="fa fa-chevron-right ops-report-arrow"></i>
				</div>`;this._panel.html(`
			<div class="ops-module-panel ops-reports-root">
				<div class="ops-module-header">
					<h4>
						<span class="ops-module-icon" style="background:#faf5ff;color:#7c3aed">
							<i class="fa fa-bar-chart"></i>
						</span>
						${__("Reports & Analytics")}
					</h4>
				</div>

				<div class="ops-report-grid">
					${e}
				</div>
			</div>
		`),this._panel.on("click",".ops-report-card",function(){let s=$(this).data("route");frappe.set_route(s)})}};frappe.provide("ops_hub");ops_hub.OpsHubApp=class{constructor(e){this.wrapper=$(e),this.page=e.page,this.layout=new _(e),this.init()}init(){this.layout.init(),this._init_modules(),this._load_context()}_init_modules(){this.dashboard=new h,this.requests=new u,this.transfers=new f,this.receiving=new m,this.reports=new v}_load_context(){frappe.call({method:"ch_erp15.ch_erp15.operations_hub_api.get_ops_context",callback:e=>{if(!e.message)return;let s=e.message;a.user=s.user,a.user_fullname=s.user_fullname,a.roles=s.roles||[],a.company=s.company,a.companies=s.companies||[],a.warehouses=s.warehouses||[],o.emit("context:loaded",a),o.emit("module:switch","dashboard")}})}destroy(){this.layout.destroy()}};})();
//# sourceMappingURL=operations_hub.bundle.AEUIDSAM.js.map
