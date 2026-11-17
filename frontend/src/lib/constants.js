export const ROLES = {
  CUSTOMER: "customer",
  PROVIDER_ADMIN: "provider_admin",
  PROVIDER_STAFF: "provider_staff",
  DEALER_ADMIN: "dealer_admin",
  DEALER_STAFF: "dealer_staff",
  AGENT: "agent",
  INSPECTOR: "inspector",
  CLAIMS_OFFICER: "claims_officer",
  ADMIN: "admin",
  SUPER_ADMIN: "super_admin",
};

export const ROLE_LABELS = {
  customer: "Customer",
  provider_admin: "Provider admin",
  provider_staff: "Provider staff",
  dealer_admin: "Dealership admin",
  dealer_staff: "Dealership staff",
  agent: "Insurance agent",
  inspector: "Vehicle inspector",
  claims_officer: "Claims officer",
  admin: "Platform admin",
  super_admin: "Super admin",
};

export const HOME_BY_ROLE = {
  customer: "/app",
  provider_admin: "/provider",
  provider_staff: "/provider",
  dealer_admin: "/dealer",
  dealer_staff: "/dealer",
  agent: "/agent",
  inspector: "/inspector",
  claims_officer: "/claims",
  admin: "/admin",
  super_admin: "/admin",
};

export const PRODUCT_CATEGORIES = [
  { value: "comprehensive", label: "Comprehensive" },
  { value: "third_party", label: "Third party only" },
  { value: "third_party_fire_theft", label: "Third party, fire & theft" },
  { value: "commercial", label: "Commercial motor" },
  { value: "motorcycle", label: "Motorcycle" },
];

export const INSURANCE_LINES = [
  { value: "motor", label: "Motor", description: "Personal vehicles, fleets, motorcycles and commercial transport.", status: "live" },
  { value: "health", label: "Health and medical", description: "Individual, family and employer medical protection.", status: "planned" },
  { value: "life", label: "Life", description: "Long-term protection for individuals, families and dependants.", status: "planned" },
  { value: "business", label: "Business and commercial", description: "Cover for organisations, operations, people and assets.", status: "planned" },
  { value: "property", label: "Property and home", description: "Homes, buildings, contents and property risks.", status: "planned" },
  { value: "travel", label: "Travel", description: "Protection for journeys, cancellations and travel emergencies.", status: "planned" },
  { value: "marine", label: "Marine and cargo", description: "Cargo, transit and commercial maritime risks.", status: "planned" },
  { value: "agriculture", label: "Agriculture", description: "Farms, livestock, crops and agricultural operations.", status: "planned" },
  { value: "accident", label: "Personal accident", description: "Financial support after accidental injury or loss.", status: "planned" },
  { value: "liability", label: "Liability", description: "Protection against legal and third-party obligations.", status: "planned" },
];

export const CLAIM_TYPES = [
  { value: "accident", label: "Accident" },
  { value: "theft", label: "Theft" },
  { value: "fire", label: "Fire" },
  { value: "third_party", label: "Third party liability" },
  { value: "windshield", label: "Windshield" },
  { value: "other", label: "Other" },
];

export const VEHICLE_CATEGORIES = [
  "saloon",
  "suv",
  "pickup",
  "van",
  "truck",
  "bus",
  "motorcycle",
  "three_wheeler",
  "other",
];

export const FUEL_TYPES = ["petrol", "diesel", "hybrid", "electric", "lpg"];
export const USAGE_TYPES = ["private", "commercial", "psv"];

export const PAYMENT_METHODS = [
  { value: "mpesa", label: "M-Pesa" },
  { value: "card", label: "Card" },
  { value: "bank", label: "Bank transfer" },
];

export const DEMO_ACCOUNTS = [
  { label: "Customer", email: "customer@example.com", password: "Customer@12345" },
  { label: "Insurer", email: "insurer@example.com", password: "Insurer@12345" },
  { label: "Claims", email: "claims@example.com", password: "Claims@12345" },
  { label: "Inspector", email: "inspector@example.com", password: "Inspector@12345" },
  { label: "Admin", email: "admin@autoinssure.local", password: "Admin@12345" },
];

export const INSPECTION_ZONES = [
  { key: "front_bumper", label: "Front bumper", position: [2.15, 0.55, 0] },
  { key: "bonnet", label: "Bonnet", position: [1.25, 1.02, 0] },
  { key: "windshield", label: "Windshield", position: [0.72, 1.52, 0] },
  { key: "front_left_door", label: "Front left door", position: [0.35, 0.92, 0.98] },
  { key: "rear_left_door", label: "Rear left door", position: [-0.75, 0.92, 0.98] },
  { key: "front_right_door", label: "Front right door", position: [0.35, 0.92, -0.98] },
  { key: "rear_right_door", label: "Rear right door", position: [-0.75, 0.92, -0.98] },
  { key: "roof", label: "Roof", position: [-0.1, 1.62, 0] },
  { key: "rear_bumper", label: "Rear bumper", position: [-2.15, 0.55, 0] },
  { key: "boot", label: "Boot / trunk", position: [-1.35, 1.02, 0] },
  { key: "rear_windshield", label: "Rear windshield", position: [-0.88, 1.52, 0] },
  { key: "left_front_wheel", label: "Left front wheel", position: [1.35, 0.3, 1.02] },
  { key: "right_front_wheel", label: "Right front wheel", position: [1.35, 0.3, -1.02] },
  { key: "left_rear_wheel", label: "Left rear wheel", position: [-1.35, 0.3, 1.02] },
  { key: "right_rear_wheel", label: "Right rear wheel", position: [-1.35, 0.3, -1.02] },
  { key: "headlights", label: "Headlights", position: [2.13, 0.72, 0.55] },
  { key: "taillights", label: "Taillights", position: [-2.13, 0.72, 0.55] },
  { key: "side_mirrors", label: "Side mirrors", position: [0.72, 1.12, 1.06] },
  { key: "interior", label: "Interior", position: [0, 1.35, 0] },
  { key: "engine", label: "Engine / mechanical", position: [1.65, 0.8, 0] },
];

export const STATUS_LABELS = {
  draft: "Draft",
  pending: "Pending",
  submitted: "Submitted",
  quoted: "Quotes received",
  selected: "Selected",
  converted: "Converted",
  received: "Received",
  expired: "Expired",
  cancelled: "Cancelled",
  under_review: "Under review",
  info_required: "Info required",
  more_info: "More info required",
  inspection_scheduled: "Inspection scheduled",
  assessment: "Assessment",
  approved: "Approved",
  rejected: "Rejected",
  settled: "Settled",
  closed: "Closed",
  withdrawn: "Withdrawn",
  policy_issued: "Policy issued",
  active: "Active",
  lapsed: "Lapsed",
  processing: "Processing",
  succeeded: "Succeeded",
  failed: "Failed",
  refunded: "Refunded",
  requested: "Requested",
  scheduled: "Scheduled",
  in_progress: "In progress",
  completed: "Completed",
  verified: "Verified",
  suspended: "Suspended",
  paid: "Paid",
  pending_verification: "Pending verification",
};
