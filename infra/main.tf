module "payment_infra" {
  source = "terraform-aws-modules/vpc/aws"

  name = "payment-system"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true

  tags = {
    Environment = "production"
  }
}

resource "aws_eks_cluster" "payment_cluster" {
  name     = "payment-system"
  role_arn = aws_iam_role.eks_cluster.arn

  vpc_config {
    subnet_ids = module.payment_infra.private_subnets
  }
}