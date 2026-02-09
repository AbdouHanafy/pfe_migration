const Button = ({ variant = 'primary', className = '', ...props }) => {
  const classes = `btn ${variant === 'ghost' ? 'btn-ghost' : 'btn-primary'} ${className}`
  return <button className={classes} {...props} />
}

export default Button
