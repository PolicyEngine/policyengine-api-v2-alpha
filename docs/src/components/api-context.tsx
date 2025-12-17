"use client";

import { createContext, useContext, useState, ReactNode } from "react";

interface ApiContextType {
  baseUrl: string;
  setBaseUrl: (url: string) => void;
}

const ApiContext = createContext<ApiContextType>({
  baseUrl: "http://localhost:8000",
  setBaseUrl: () => {},
});

export function ApiProvider({ children }: { children: ReactNode }) {
  const [baseUrl, setBaseUrl] = useState("http://localhost:8000");

  return (
    <ApiContext.Provider value={{ baseUrl, setBaseUrl }}>
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  return useContext(ApiContext);
}
