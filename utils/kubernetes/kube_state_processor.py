from functools import partial


class KubeStateProcessor:
    def __init__(self, kubernetes_check):
        self.kube_check = kubernetes_check
        self.log = self.kube_check.log
        self.gauge = partial(self.kube_check.publish_gauge, self.kube_check)

    def process(self, message, **kwargs):
        """
        Search this class for a method with the same name of the message and
        invoke it. Log some info if method was not found.
        """
        try:
            getattr(self, message.name)(message, **kwargs)
        except AttributeError:
            self.log.debug("Unable to handle metric: {}".format(message.name))

    def _eval_metric_condition(self, metric):
        """
        Some metrics contains conditions, labels that have "condition" as name and "true", "false", or "unknown"
        as value. The metric value is expected to be a gauge equal to 0 or 1 in this case.

        This function acts as an helper to iterate and evaluate metrics containing conditions
        and returns a tuple containing the name of the condition and the boolean value.
        For example:

        metric {
          label {
            name: "condition"
            value: "true"
          }
          # other labels here
          gauge {
            value: 1.0
          }
        }

        would return `("true", True)`.

        Returns `None, None` if metric has no conditions.
        """
        val = bool(metric.gauge.value)
        for label in metric.label:
            if label.name == 'condition':
                return label.value, val

        return None, None

    def _extract_label_value(self, name, labels):
        """
        Search for `name` in labels name and returns
        corresponding value.
        Returns None if name was not found.
        """
        for label in labels:
            if label.name == name:
                return label.value
        return None

    def kube_node_status_capacity_cpu_cores(self, message, **kwargs):
        metric_name = 'kubernetes.node.cpu_capacity'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(metric.label[0].value)]
            self.gauge(metric_name, val, tags)

    def kube_node_status_capacity_memory_bytes(self, message, **kwargs):
        metric_name = 'kubernetes.node.memory_capacity'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            self.gauge(metric_name, val, tags)

    def kube_node_status_capacity_pods(self, message, **kwargs):
        metric_name = 'kubernetes.node.pods_capacity'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            self.gauge(metric_name, val, tags)

    def kube_node_status_allocateable_cpu_cores(self, message, **kwargs):
        metric_name = 'kubernetes.node.cpu_allocatable'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            self.gauge(metric_name, val, tags)

    def kube_node_status_allocateable_memory_bytes(self, message, **kwargs):
        metric_name = 'kubernetes.node.memory_allocatable'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            self.gauge(metric_name, val, tags)

    def kube_node_status_allocateable_pods(self, message, **kwargs):
        metric_name = 'kubernetes.node.pods_allocatable'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            self.gauge(metric_name, val, tags)

    def kube_deployment_status_replicas_available(self, message, **kwargs):
        metric_name = 'kubernetes.deployment.replicas_available'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['{}:{}'.format(label.name, label.value) for label in metric.label]
            self.gauge(metric_name, val, tags)

    def kube_deployment_status_replicas_unavailable(self, message, **kwargs):
        metric_name = 'kubernetes.deployment.replicas_unavailable'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['{}:{}'.format(label.name, label.value) for label in metric.label]
            self.gauge(metric_name, val, tags)

    def kube_deployment_status_replicas_updated(self, message, **kwargs):
        metric_name = 'kubernetes.deployment.replicas_updated'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['{}:{}'.format(label.name, label.value) for label in metric.label]
            self.gauge(metric_name, val, tags)

    def kube_deployment_spec_replicas(self, message, **kwargs):
        metric_name = 'kubernetes.deployment.replicas_desired'
        for metric in message.metric:
            val = metric.gauge.value
            tags = ['{}:{}'.format(label.name, label.value) for label in metric.label]
            self.gauge(metric_name, val, tags)

    def kube_node_status_ready(self, message, **kwargs):
        service_check_name = 'kube_node_status_ready'
        for metric in message.metric:
            name, val = self._eval_metric_condition(metric)
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            if name == 'true' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.OK, tags=tags)
            elif name == 'false' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.CRITICAL, tags=tags)
            elif name == 'unknown' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.UNKNOWN, tags=tags)

    def kube_node_status_out_of_disk(self, message, **kwargs):
        service_check_name = 'kube_node_status_out_of_disk'
        for metric in message.metric:
            name, val = self._eval_metric_condition(metric)
            tags = ['host:{}'.format(self._extract_label_value("node", metric.label))]
            if name == 'true' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.CRITICAL, tags=tags)
            elif name == 'false' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.OK, tags=tags)
            elif name == 'unknown' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.UNKNOWN, tags=tags)

    def kube_pod_status_ready(self, message, **kwargs):
        """
        We only send service checks for those pods explicitly listed in the
        configuration file.
        """
        service_check_name = 'kube_pod_status_ready'
        configured_pods = kwargs.get('instance', {}).get('status_ready_for_pods')
        if configured_pods is None:
            self.log.debug('no pods configured, kube_pod_status_ready has nothing to do, returning...')
            return

        for metric in message.metric:
            pod_name = self._extract_label_value("pod", metric.label)
            if pod_name not in configured_pods:
                continue

            name, val = self._eval_metric_condition(metric)

            tags = [
                'namespace:{}'.format(self._extract_label_value("namespace", metric.label)),
                'pod:{}'.format(pod_name)
            ]

            if name == 'true' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.OK, tags=tags)
            if name == 'false' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.CRITICAL, tags=tags)
            elif name == 'unknown' and val:
                self.kube_check.service_check(service_check_name, self.kube_check.UNKNOWN, tags=tags)
