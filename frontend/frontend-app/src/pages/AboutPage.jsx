const AboutPage = () => {
  return (
    <div className="page">
      <h2>About This Project</h2>
      <p>
        This UI drives a smart VM migration pipeline: discovery, compatibility analysis,
        conversion planning, and OpenShift Virtualization integration.
      </p>
      <ul>
        <li>Source: KVM/VMware (discovery + disk export)</li>
        <li>Target: OpenShift Virtualization (KubeVirt + CDI)</li>
        <li>Automation: API-driven workflows</li>
      </ul>
    </div>
  )
}

export default AboutPage
