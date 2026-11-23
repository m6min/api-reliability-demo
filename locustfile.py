from locust import HttpUser, constant_throughput, task


class ProductApiUser(HttpUser):
    wait_time = constant_throughput(10)
    @task
    def get_products(self) -> None:
        self.client.get("/api/products/",name="GET api/products")
