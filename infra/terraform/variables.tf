variable "aws_region" {
  type    = string
  default = "us-east-1"
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
