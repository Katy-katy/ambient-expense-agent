terraform {
  backend "gcs" {
    bucket = "project-285f4295-92e7-4bf0-94f-terraform-state"
    prefix = "ambient-expense-agent/dev"
  }
}
