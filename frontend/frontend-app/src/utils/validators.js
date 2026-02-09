export const isNonEmpty = (value) => Boolean(value && value.trim())

export const validateCredentials = ({ matricule, password }) => {
  const errors = []
  if (!isNonEmpty(matricule)) errors.push('Matricule is required')
  if (!isNonEmpty(password)) errors.push('Password is required')
  return errors
}
