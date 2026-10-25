import { useEffect } from 'react'

const SITE = 'Nepal Disaster Twin'

export default function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} — ${SITE}` : SITE
  }, [title])
}
