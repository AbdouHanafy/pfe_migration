const JsonBlock = ({ data }) => {
  return <pre className="code">{data ? JSON.stringify(data, null, 2) : ''}</pre>
}

export default JsonBlock
