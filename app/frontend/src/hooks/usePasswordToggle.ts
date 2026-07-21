import { useState } from 'react';

export function usePasswordToggle() {
  const [isVisible, setIsVisible] = useState(false);

  const toggle = () => setIsVisible((visible) => !visible);

  return { isVisible, toggle, inputType: isVisible ? 'text' : 'password' } as const;
}
