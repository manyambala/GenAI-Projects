# Kubernetes Internal Documentation

## 1. Introduction to Kubernetes
Kubernetes (K8s) is an open-source system for automating deployment, scaling, and management of containerized applications. Originally developed by Google, it is now maintained by the Cloud Native Computing Foundation (CNCF). In our organization, Kubernetes is the standard platform for running all microservices, stateful applications, and batch processing jobs.

This document serves as the authoritative guide for developers and operators managing workloads on our internal Kubernetes clusters.

## 2. Core Concepts

### Pods
A Pod is the smallest deployable computing unit in Kubernetes. It encapsulates one or more containers, storage resources, a unique network IP, and options that govern how the containers should run.
Containers within a Pod share the same network namespace (IP and port space) and can communicate via `localhost`.

### Deployments
A Deployment provides declarative updates for Pods and ReplicaSets. You describe a desired state in a Deployment, and the Deployment Controller changes the actual state to the desired state at a controlled rate.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend-app
        image: our-registry.internal/backend:v1.2.0
        ports:
        - containerPort: 8080
```

### Services
A Service in Kubernetes is an abstraction which defines a logical set of Pods and a policy by which to access them. The set of Pods targeted by a Service is usually determined by a selector.

### ConfigMaps and Secrets
- **ConfigMap**: An API object used to store non-confidential data in key-value pairs. Pods can consume ConfigMaps as environment variables, command-line arguments, or as configuration files in a volume.
- **Secret**: An object that contains a small amount of sensitive data such as a password, a token, or a key. Using a Secret means that you don't need to include confidential data in your application code.

## 3. Deployment Strategies

### Rolling Update
The default strategy. It replaces old Pods with new ones gradually, ensuring zero downtime. You can configure `maxUnavailable` and `maxSurge` to control the update process.

### Blue-Green Deployment
In a Blue-Green deployment, you maintain two identical environments. Blue is the current version, and Green is the new version. Once Green is tested and verified, traffic is switched from Blue to Green. This requires a custom ingress controller or service mesh route update.

### Canary Deployment
Canary deployments release a new version to a small percentage of users before rolling it out to the entire infrastructure. This is often achieved using Istio or an Ingress controller supporting weighted routing.

## 4. Horizontal Pod Autoscaler (HPA)
The HPA automatically scales the number of Pods in a replication controller, deployment, replica set or stateful set based on observed CPU utilization or with custom metrics support, on some other application-provided metrics.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## 5. Resource Management
To ensure stable clusters, every container must specify compute resource requests and limits.

### Requests and Limits
- **Requests**: The guaranteed amount of resource (CPU/Memory) a container needs. The scheduler uses this to decide which node to place the Pod on.
- **Limits**: The maximum amount of resource a container is allowed to use. If a container exceeds its memory limit, it may be terminated (OOMKilled). If it exceeds CPU, it will be throttled.

### QoS Classes
- **Guaranteed**: Requests == Limits for both CPU and Memory. Highest priority.
- **Burstable**: Requests < Limits. Medium priority.
- **BestEffort**: No requests or limits specified. Lowest priority, first to be evicted.

## 6. Networking

### ClusterIP
The default Service type. It exposes the Service on a cluster-internal IP. Choosing this value makes the Service only reachable from within the cluster.

### NodePort
Exposes the Service on each Node's IP at a static port (the NodePort). A ClusterIP Service, to which the NodePort Service routes, is automatically created.

### LoadBalancer
Exposes the Service externally using a cloud provider's load balancer. NodePort and ClusterIP Services, to which the external load balancer routes, are automatically created.

### Ingress
An API object that manages external access to the services in a cluster, typically HTTP. Ingress may provide load balancing, SSL termination and name-based virtual hosting.

## 7. Storage

### PersistentVolumes (PV)
A piece of storage in the cluster that has been provisioned by an administrator or dynamically provisioned using Storage Classes.

### PersistentVolumeClaims (PVC)
A request for storage by a user. It is similar to a Pod. Pods consume node resources and PVCs consume PV resources.

### StorageClasses
Provides a way for administrators to describe the "classes" of storage they offer. Different classes might map to quality-of-service levels, or to backup policies.

## 8. Monitoring and Logging Best Practices
- **Monitoring**: We use Prometheus for scraping metrics and Grafana for dashboards. Ensure your applications expose a `/metrics` endpoint in Prometheus format.
- **Logging**: We employ a fluent-bit DaemonSet to collect logs from stdout/stderr of all containers. Logs are shipped to our centralized ELK stack. Never log sensitive information (PII, credentials).

## 9. Troubleshooting Common Issues

### CrashLoopBackOff
Indicates that a container repeatedly crashes after starting. 
- **Fix**: Check `kubectl logs <pod-name>` to see the application startup error.

### OOMKilled
The container exceeded its memory limit and was killed by the kernel.
- **Fix**: Analyze memory dumps, check for memory leaks, and appropriately increase the memory `limit` in the Deployment spec.

### ImagePullBackOff
Kubernetes cannot pull the container image.
- **Fix**: Verify the image tag exists in the registry. Check if `imagePullSecrets` are correctly configured.

## 10. Conclusion
Following these guidelines ensures that our services remain highly available, scalable, and manageable. For questions, consult the Platform Engineering team.
