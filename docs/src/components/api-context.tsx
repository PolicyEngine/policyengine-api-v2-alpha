"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface ApiContextType {
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}

const ApiContext = createContext<ApiContextType>({
  baseUrl: "https://v2.api.policyengine.org",
  setBaseUrl: () => {},
});

export function ApiProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrl] = useState("https://v2.api.policyengine.org");

  return (
    <ApiContext.Provider value={{ baseUrl, setBaseUrl }}>
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  return useContext(ApiContext);
}
