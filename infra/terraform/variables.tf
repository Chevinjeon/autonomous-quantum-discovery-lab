variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "project_name" {
  type    = string
  default = "synqubi"
}

variable "default_llm_provider" {
  type    = string
  default = "xAI"
}

variable "default_llm_model" {
  type    = string
  default = "grok-4-0709"
}

variable "frontend_url" {
  type        = string
  description = "Amplify frontend URL for CORS"
  default     = ""
}
