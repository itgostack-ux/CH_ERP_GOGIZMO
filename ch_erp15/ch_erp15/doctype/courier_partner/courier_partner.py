import frappe
from frappe.model.document import Document


class CourierPartner(Document):
	def get_tracking_url(self, tracking_number):
		"""Return full tracking URL for given tracking number."""
		if self.tracking_url_template and tracking_number:
			return self.tracking_url_template.replace("{tracking_number}", tracking_number)
		return ""
