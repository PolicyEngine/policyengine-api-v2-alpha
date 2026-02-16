"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface ApiContextType {
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}

const defaultBaseUrl = process.env.NEXT_PUBLIC_API_URL || "https://v2.api.policyengine.org";

const ApiContext = createContext<ApiContextType>({
  baseUrl: defaultBaseUrl,
  setBaseUrl: () => {},
});

export function ApiProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);

  return (
    <ApiContext.Provider value={{ baseUrl, setBaseUrl }}>
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  return useContext(ApiContext);
}
