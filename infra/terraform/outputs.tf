output "backend_url" {
  value = aws_apprunner_service.backend.service_url
}

output "ecr_repository" {
  value = aws_ecr_repository.backend.repository_url
}
