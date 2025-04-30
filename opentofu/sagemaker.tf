resource "aws_sagemaker_model" "echoprime_model" {
  name               = "${local.name_prefix}-model"
  execution_role_arn = module.iam.sagemaker_role_arn

  primary_container {
    image          = "${module.ecr.repository_url}@${data.aws_ecr_image.echoprime_image.image_digest}"
    model_data_url = "s3://${module.storage.bucket_name}/model/model.tar.gz"
  }

  tags = local.common_tags
}

resource "aws_sagemaker_endpoint_configuration" "echoprime_endpoint_config" {
  name = "${local.name_prefix}-endpoint-config"

  production_variants {
    variant_name           = "default"
    model_name             = aws_sagemaker_model.echoprime_model.name
    initial_instance_count = 1
    instance_type          = "ml.m5.large"
  }

  async_inference_config {
    output_config {
      s3_output_path = "s3://${module.storage.bucket_name}/outputs/"
      notification_config {
        success_topic = aws_sns_topic.sagemaker_success.arn
        error_topic   = aws_sns_topic.sagemaker_error.arn
      }
    }
  }

  tags = local.common_tags
}

resource "aws_sagemaker_endpoint" "echoprime_endpoint" {
  name                 = "${local.name_prefix}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.echoprime_endpoint_config.name

  tags = local.common_tags
}

resource "aws_sns_topic" "sagemaker_success" {
  name = "${local.name_prefix}-sagemaker-success"
  tags = local.common_tags
}

resource "aws_sns_topic" "sagemaker_error" {
  name = "${local.name_prefix}-sagemaker-error"
  tags = local.common_tags
}

resource "aws_appautoscaling_target" "sagemaker_endpoint_target" {
  max_capacity       = 5
  min_capacity       = 1
  resource_id        = "endpoint/${aws_sagemaker_endpoint.echoprime_endpoint.name}/variant/default"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker_endpoint_policy" {
  name               = "${local.name_prefix}-autoscaling-policy"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker_endpoint_target.resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker_endpoint_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker_endpoint_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value       = 5000
    scale_in_cooldown  = 300
    scale_out_cooldown = 300
  }
}
