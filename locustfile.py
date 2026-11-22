from locust import HttpUser, between, task


class ProductApiUser(HttpUser):
    wait_time = between(1,3)
    @task
    def get_products(self) -> None:
        self.client.get("/api/products/",name="GET api/products")
