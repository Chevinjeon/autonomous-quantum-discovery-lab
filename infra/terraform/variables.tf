variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "synqubi"
}

variable "kinesis_stream_name" {
  type    = string
  default = "synqubi-market-ticks"
}

variable "dynamodb_table_name" {
  type    = string
  default = "synqubi-market-latest"
}

variable "solver_desired_count" {
  type    = number
  default = 0
}
