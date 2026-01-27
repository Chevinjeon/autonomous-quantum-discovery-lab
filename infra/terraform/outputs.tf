output "kinesis_stream_name" {
  value = aws_kinesis_stream.market_ticks.name
}

output "dynamodb_table_name" {
  value = aws_dynamodb_table.latest_market.name
}

output "solver_ecr_repository" {
  value = aws_ecr_repository.solver_repo.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.solver_cluster.name
}
