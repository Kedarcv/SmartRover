"use client"

import type React from "react"

import { useState, useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import {
  Activity,
  MapPin,
  Navigation,
  Radar,
  AlertTriangle,
  Play,
  Square,
  Wifi,
  WifiOff,
  Cpu,
  HardDrive,
  Bluetooth,
  BluetoothOff,
  Shield,
  LogOut,
  Settings,
  BarChart3,
  FileText,
  Eye,
  EyeOff,
  Search,
  RefreshCw,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
} from "lucide-react"

// Safe fetch utility
async function safeFetch<T>(url: string, opts?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, {
      ...opts,
      cache: "no-store",
      credentials: "include",
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = (await res.json()) as T
    return (json as any).success === false ? null : (json as T)
  } catch {
    return null
  }
}

// Local storage utilities
const STORAGE_KEYS = {
  USER: "smartrover_user",
  VEHICLES: "smartrover_vehicles",
  ACTIVE_VEHICLE: "smartrover_active_vehicle",
}

interface VehicleData {
  timestamp: number
  position: [number, number]
  heading: number
  sensor_data: {
    ultrasonic: number[]
    camera_available: boolean
  }
  action_data: {
    action: string
    action_confidence: number
    speed: number
    obstacle_detected: boolean
    obstacle_confidence: number
  }
  map_data: {
    robot_position: [number, number]
    robot_heading: number
    path_history: [number, number][]
    obstacles: any[]
    map_region: number[][][]
    timestamp: number
  }
  system_status: {
    running: boolean
    camera_available: boolean
    emergency_stop: boolean
  }
  connection_info: {
    wifi_connected: boolean
    bluetooth_connected: boolean
    last_update: number
  }
}

interface SystemInfo {
  platform: string
  hostname: string
  cpu: {
    percent: number
    count: number
    temperature: number | null
  }
  memory: {
    total: number
    available: number
    percent: number
    used: number
  }
  disk: {
    total: number
    used: number
    free: number
    percent: number
  }
  network: Record<string, any>
  uptime: number
  vehicle_running: boolean
  bluetooth_clients: number
  timestamp: number
}

interface Vehicle {
  id: string
  name: string
  url: string
  status: "connected" | "disconnected" | "connecting"
  lastSeen?: number
  type: "manual" | "discovered"
}

interface User {
  email: string
  loginTime: number
}

// Standalone authentication - no server required
const VALID_USERS = {
  "cvlised360@gmail.com": "Cvlised@360",
  "admin@smartrover.com": "admin123",
  "operator@smartrover.com": "operator123",
}

export default function MiningDashboard() {
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [showLogin, setShowLogin] = useState(false)
  const [loginForm, setLoginForm] = useState({ email: "", password: "" })
  const [showPassword, setShowPassword] = useState(false)

  // Vehicle management state
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [activeVehicle, setActiveVehicle] = useState<Vehicle | null>(null)
  const [showVehicleDialog, setShowVehicleDialog] = useState(false)
  const [newVehicleForm, setNewVehicleForm] = useState({ name: "", url: "" })
  const [isScanning, setIsScanning] = useState(false)

  // Vehicle data state
  const [vehicleData, setVehicleData] = useState<VehicleData | null>(null)
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [isBluetoothConnected, setIsBluetoothConnected] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [logs, setLogs] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState("vehicles")

  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    // Check if user is already logged in
    const savedUser = localStorage.getItem(STORAGE_KEYS.USER)
    if (savedUser) {
      const userData = JSON.parse(savedUser)
      setUser(userData)
      setIsAuthenticated(true)
      loadVehicles()
    } else {
      setShowLogin(true)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated && activeVehicle && activeVehicle.status === "connected") {
      const interval = setInterval(() => {
        fetchVehicleData()
        fetchSystemInfo()
        if (activeTab === "logs") {
          fetchLogs()
        }
      }, 1000)

      return () => clearInterval(interval)
    }
  }, [activeVehicle, isAuthenticated, activeTab])

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const email = loginForm.email.toLowerCase().trim()
      const password = loginForm.password

      if (VALID_USERS[email as keyof typeof VALID_USERS] === password) {
        const userData: User = {
          email,
          loginTime: Date.now(),
        }

        localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userData))
        setUser(userData)
        setIsAuthenticated(true)
        setShowLogin(false)
        setLoginForm({ email: "", password: "" })
        loadVehicles()
      } else {
        alert("Invalid credentials")
      }
    } catch (error) {
      alert("Login failed")
    } finally {
      setIsLoading(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem(STORAGE_KEYS.USER)
    localStorage.removeItem(STORAGE_KEYS.ACTIVE_VEHICLE)
    setIsAuthenticated(false)
    setUser(null)
    setActiveVehicle(null)
    setVehicleData(null)
    setSystemInfo(null)
    setIsConnected(false)
    setShowLogin(true)
  }

  const loadVehicles = () => {
    const savedVehicles = localStorage.getItem(STORAGE_KEYS.VEHICLES)
    const savedActiveVehicle = localStorage.getItem(STORAGE_KEYS.ACTIVE_VEHICLE)

    if (savedVehicles) {
      const vehicleList = JSON.parse(savedVehicles)
      setVehicles(vehicleList)
    }

    if (savedActiveVehicle) {
      const activeVehicleData = JSON.parse(savedActiveVehicle)
      setActiveVehicle(activeVehicleData)
    }
  }

  const saveVehicles = (vehicleList: Vehicle[]) => {
    localStorage.setItem(STORAGE_KEYS.VEHICLES, JSON.stringify(vehicleList))
    setVehicles(vehicleList)
  }

  const addVehicle = () => {
    if (!newVehicleForm.name || !newVehicleForm.url) {
      alert("Please fill in all fields")
      return
    }

    const newVehicle: Vehicle = {
      id: Date.now().toString(),
      name: newVehicleForm.name,
      url: newVehicleForm.url,
      status: "disconnected",
      type: "manual",
    }

    const updatedVehicles = [...vehicles, newVehicle]
    saveVehicles(updatedVehicles)
    setNewVehicleForm({ name: "", url: "" })
    setShowVehicleDialog(false)
  }

  const removeVehicle = (vehicleId: string) => {
    const updatedVehicles = vehicles.filter((v) => v.id !== vehicleId)
    saveVehicles(updatedVehicles)

    if (activeVehicle?.id === vehicleId) {
      setActiveVehicle(null)
      localStorage.removeItem(STORAGE_KEYS.ACTIVE_VEHICLE)
    }
  }

  const connectToVehicle = async (vehicle: Vehicle) => {
    setIsLoading(true)

    // Update vehicle status to connecting
    const updatedVehicles = vehicles.map((v) => (v.id === vehicle.id ? { ...v, status: "connecting" as const } : v))
    saveVehicles(updatedVehicles)

    try {
      // Test connection to vehicle
      const response = await fetch(`${vehicle.url}/api/system-status`, {
        method: "GET",
        timeout: 5000,
      } as any)

      if (response.ok) {
        const connectedVehicle = { ...vehicle, status: "connected" as const, lastSeen: Date.now() }

        // Update vehicles list
        const finalVehicles = vehicles.map((v) =>
          v.id === vehicle.id ? connectedVehicle : { ...v, status: "disconnected" as const },
        )
        saveVehicles(finalVehicles)

        // Set as active vehicle
        setActiveVehicle(connectedVehicle)
        localStorage.setItem(STORAGE_KEYS.ACTIVE_VEHICLE, JSON.stringify(connectedVehicle))
        setIsConnected(true)
        setActiveTab("dashboard")
      } else {
        throw new Error("Connection failed")
      }
    } catch (error) {
      // Update vehicle status to disconnected
      const failedVehicles = vehicles.map((v) => (v.id === vehicle.id ? { ...v, status: "disconnected" as const } : v))
      saveVehicles(failedVehicles)
      alert(`Failed to connect to ${vehicle.name}`)
    } finally {
      setIsLoading(false)
    }
  }

  const disconnectFromVehicle = () => {
    if (activeVehicle) {
      const updatedVehicles = vehicles.map((v) =>
        v.id === activeVehicle.id ? { ...v, status: "disconnected" as const } : v,
      )
      saveVehicles(updatedVehicles)
    }

    setActiveVehicle(null)
    setIsConnected(false)
    setVehicleData(null)
    setSystemInfo(null)
    localStorage.removeItem(STORAGE_KEYS.ACTIVE_VEHICLE)
    setActiveTab("vehicles")
  }

  const scanForVehicles = async () => {
    setIsScanning(true)
    const discoveredVehicles: Vehicle[] = []

    // Common IP ranges and ports for mining vehicles
    const ipRanges = ["192.168.1.", "192.168.0.", "10.0.0.", "172.16.0."]
    const ports = [5000, 8080, 3000, 8000]

    try {
      for (const range of ipRanges) {
        for (let i = 1; i <= 254; i++) {
          for (const port of ports) {
            const url = `http://${range}${i}:${port}`

            try {
              const controller = new AbortController()
              const timeoutId = setTimeout(() => controller.abort(), 1000)

              const response = await fetch(`${url}/api/system-status`, {
                method: "GET",
                signal: controller.signal,
              })

              clearTimeout(timeoutId)

              if (response.ok) {
                const data = await response.json()
                if (data.success) {
                  const existingVehicle = vehicles.find((v) => v.url === url)
                  if (!existingVehicle) {
                    discoveredVehicles.push({
                      id: `discovered_${Date.now()}_${i}`,
                      name: `Vehicle ${range}${i}:${port}`,
                      url,
                      status: "disconnected",
                      type: "discovered",
                    })
                  }
                }
              }
            } catch (error) {
              // Ignore connection errors during scanning
            }
          }
        }
      }

      if (discoveredVehicles.length > 0) {
        const updatedVehicles = [...vehicles, ...discoveredVehicles]
        saveVehicles(updatedVehicles)
        alert(`Discovered ${discoveredVehicles.length} new vehicle(s)`)
      } else {
        alert("No new vehicles discovered")
      }
    } catch (error) {
      alert("Scan failed")
    } finally {
      setIsScanning(false)
    }
  }

  const fetchVehicleData = async () => {
    if (!activeVehicle) return

    const result = await safeFetch<{ success: boolean; data: VehicleData }>(`${activeVehicle.url}/api/vehicle-status`)

    if (result?.success) {
      setVehicleData(result.data)
      setIsConnected(true)
      setIsBluetoothConnected(result.data.connection_info?.bluetooth_connected || false)

      // Update last seen
      const updatedVehicle = { ...activeVehicle, lastSeen: Date.now() }
      setActiveVehicle(updatedVehicle)
      localStorage.setItem(STORAGE_KEYS.ACTIVE_VEHICLE, JSON.stringify(updatedVehicle))
    } else {
      setIsConnected(false)
      setVehicleData(null)
    }
  }

  const fetchSystemInfo = async () => {
    if (!activeVehicle || !isConnected) return

    const result = await safeFetch<{ success: boolean; data: SystemInfo }>(`${activeVehicle.url}/api/system-info`)

    if (result?.success) {
      setSystemInfo(result.data)
    } else {
      setSystemInfo(null)
    }
  }

  const fetchLogs = async () => {
    if (!activeVehicle) return

    const result = await safeFetch<{ success: boolean; data: { logs: string[] } }>(
      `${activeVehicle.url}/api/logs?lines=50`,
    )

    if (result?.success) {
      setLogs(result.data.logs)
    }
  }

  const sendVehicleCommand = async (command: string) => {
    if (!activeVehicle) return

    setIsLoading(true)
    try {
      const response = await fetch(`${activeVehicle.url}/api/vehicle-control`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({ command }),
      })

      const result = await response.json()
      if (result.success) {
        console.log(result.message)
      }
    } catch (error) {
      console.error("Failed to send command:", error)
    } finally {
      setIsLoading(false)
    }
  }

  const drawMap = () => {
    if (!canvasRef.current || !vehicleData?.map_data.map_region) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const mapRegion = vehicleData.map_data.map_region
    const imageData = ctx.createImageData(canvas.width, canvas.height)

    // Convert map data to image data
    for (let y = 0; y < Math.min(canvas.height, mapRegion.length); y++) {
      for (let x = 0; x < Math.min(canvas.width, mapRegion[y]?.length || 0); x++) {
        const pixelIndex = (y * canvas.width + x) * 4
        const mapValue = mapRegion[y][x]

        if (Array.isArray(mapValue) && mapValue.length >= 3) {
          imageData.data[pixelIndex] = mapValue[0] // R
          imageData.data[pixelIndex + 1] = mapValue[1] // G
          imageData.data[pixelIndex + 2] = mapValue[2] // B
          imageData.data[pixelIndex + 3] = 255 // A
        } else {
          // Grayscale value
          const value = typeof mapValue === "number" ? mapValue : 0
          imageData.data[pixelIndex] = value
          imageData.data[pixelIndex + 1] = value
          imageData.data[pixelIndex + 2] = value
          imageData.data[pixelIndex + 3] = 255
        }
      }
    }

    ctx.putImageData(imageData, 0, 0)
  }

  useEffect(() => {
    drawMap()
  }, [vehicleData])

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${days}d ${hours}h ${minutes}m`
  }

  const formatBytes = (bytes: number) => {
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"]
    if (bytes === 0) return "0 Bytes"
    const i = Math.floor(Math.log(bytes) / Math.log(1024))
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i]
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 flex items-center justify-center p-6">
        <Dialog open={showLogin} onOpenChange={setShowLogin}>
          <DialogContent className="sm:max-w-md bg-gray-800 border-gray-700">
            <DialogHeader>
              <DialogTitle className="text-white flex items-center gap-2">
                <Shield className="w-5 h-5" />
                SmartRover Dashboard
              </DialogTitle>
              <DialogDescription className="text-gray-400">
                Sign in to access the mining vehicle control dashboard
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-white">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={loginForm.email}
                  onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                  className="bg-gray-700 border-gray-600 text-white"
                  placeholder="Enter your email"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-white">
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                    className="bg-gray-700 border-gray-600 text-white pr-10"
                    placeholder="Enter your password"
                    required
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 text-gray-400 hover:text-white"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
              <Button type="submit" disabled={isLoading} className="w-full">
                {isLoading ? "Signing In..." : "Sign In"}
              </Button>
              <div className="text-xs text-gray-400 text-center">
                Demo accounts: cvlised360@gmail.com, admin@smartrover.com, operator@smartrover.com
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white">
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              SmartRover Dashboard
            </h1>
            <p className="text-gray-400">
              {activeVehicle ? `Connected to: ${activeVehicle.name}` : "Select a vehicle to monitor"}
            </p>
          </div>
          <div className="flex items-center gap-4">
            {activeVehicle && (
              <div className="flex items-center gap-2">
                <Badge variant={isConnected ? "default" : "destructive"} className="flex items-center gap-1">
                  {isConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                  WiFi
                </Badge>
                <Badge variant={isBluetoothConnected ? "default" : "secondary"} className="flex items-center gap-1">
                  {isBluetoothConnected ? <Bluetooth className="w-3 h-3" /> : <BluetoothOff className="w-3 h-3" />}
                  Bluetooth
                </Badge>
              </div>
            )}
            <div className="text-sm text-gray-400">{user?.email}</div>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>

        {/* Connection Status Alert */}
        {activeVehicle && !isConnected && (
          <Alert className="border-red-500 bg-red-500/10">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>Connection lost to {activeVehicle.name}. Attempting to reconnect...</AlertDescription>
          </Alert>
        )}

        {/* Main Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-5 bg-gray-800">
            <TabsTrigger value="vehicles" className="flex items-center gap-2">
              <Settings className="w-4 h-4" />
              Vehicles
            </TabsTrigger>
            <TabsTrigger value="dashboard" className="flex items-center gap-2" disabled={!activeVehicle}>
              <BarChart3 className="w-4 h-4" />
              Dashboard
            </TabsTrigger>
            <TabsTrigger value="control" className="flex items-center gap-2" disabled={!activeVehicle}>
              <Settings className="w-4 h-4" />
              Control
            </TabsTrigger>
            <TabsTrigger value="system" className="flex items-center gap-2" disabled={!activeVehicle}>
              <Cpu className="w-4 h-4" />
              System
            </TabsTrigger>
            <TabsTrigger value="logs" className="flex items-center gap-2" disabled={!activeVehicle}>
              <FileText className="w-4 h-4" />
              Logs
            </TabsTrigger>
          </TabsList>

          {/* Vehicles Tab */}
          <TabsContent value="vehicles" className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">Vehicle Management</h2>
              <div className="flex gap-2">
                <Button onClick={scanForVehicles} disabled={isScanning} variant="outline">
                  {isScanning ? (
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4 mr-2" />
                  )}
                  {isScanning ? "Scanning..." : "Scan Network"}
                </Button>
                <Button onClick={() => setShowVehicleDialog(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Add Vehicle
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {vehicles.map((vehicle) => (
                <Card key={vehicle.id} className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">{vehicle.name}</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            vehicle.status === "connected"
                              ? "default"
                              : vehicle.status === "connecting"
                                ? "secondary"
                                : "outline"
                          }
                          className="flex items-center gap-1"
                        >
                          {vehicle.status === "connected" && <CheckCircle className="w-3 h-3" />}
                          {vehicle.status === "connecting" && <RefreshCw className="w-3 h-3 animate-spin" />}
                          {vehicle.status === "disconnected" && <XCircle className="w-3 h-3" />}
                          {vehicle.status}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeVehicle(vehicle.id)}
                          className="text-red-400 hover:text-red-300"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    <CardDescription>{vehicle.url}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="flex gap-2">
                      {vehicle.status === "connected" && activeVehicle?.id === vehicle.id ? (
                        <Button onClick={disconnectFromVehicle} variant="outline" className="flex-1 bg-transparent">
                          Disconnect
                        </Button>
                      ) : (
                        <Button
                          onClick={() => connectToVehicle(vehicle)}
                          disabled={vehicle.status === "connecting" || isLoading}
                          className="flex-1"
                        >
                          {vehicle.status === "connecting" ? "Connecting..." : "Connect"}
                        </Button>
                      )}
                    </div>
                    {vehicle.lastSeen && (
                      <p className="text-xs text-gray-400 mt-2">
                        Last seen: {new Date(vehicle.lastSeen).toLocaleString()}
                      </p>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>

            {vehicles.length === 0 && (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardContent className="text-center py-12">
                  <p className="text-gray-400 mb-4">No vehicles configured</p>
                  <Button onClick={() => setShowVehicleDialog(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Add Your First Vehicle
                  </Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Dashboard Tab */}
          <TabsContent value="dashboard" className="space-y-6">
            {activeVehicle && isConnected ? (
              <>
                {/* Status Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Current Action</CardTitle>
                      <Navigation className="h-4 w-4 text-blue-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-blue-400">
                        {vehicleData?.action_data.action?.toUpperCase() || "N/A"}
                      </div>
                      <p className="text-xs text-gray-400">
                        Confidence: {((vehicleData?.action_data.action_confidence || 0) * 100).toFixed(1)}%
                      </p>
                    </CardContent>
                  </Card>

                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Speed</CardTitle>
                      <Activity className="h-4 w-4 text-green-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-green-400">
                        {((vehicleData?.action_data.speed || 0) * 100).toFixed(1)}%
                      </div>
                      <Progress value={(vehicleData?.action_data.speed || 0) * 100} className="mt-2" />
                    </CardContent>
                  </Card>

                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">Position</CardTitle>
                      <MapPin className="h-4 w-4 text-purple-400" />
                    </CardHeader>
                    <CardContent>
                      <div className="text-lg font-bold text-purple-400">
                        X: {vehicleData?.position[0]?.toFixed(1) || "0.0"}
                      </div>
                      <div className="text-lg font-bold text-purple-400">
                        Y: {vehicleData?.position[1]?.toFixed(1) || "0.0"}
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">System Status</CardTitle>
                      <Activity
                        className={`h-4 w-4 ${vehicleData?.system_status.running ? "text-green-400" : "text-red-400"}`}
                      />
                    </CardHeader>
                    <CardContent>
                      <div
                        className={`text-2xl font-bold ${vehicleData?.system_status.running ? "text-green-400" : "text-red-400"}`}
                      >
                        {vehicleData?.system_status.running ? "RUNNING" : "STOPPED"}
                      </div>
                      <p className="text-xs text-gray-400">
                        Camera: {vehicleData?.sensor_data.camera_available ? "Available" : "Unavailable"}
                      </p>
                    </CardContent>
                  </Card>
                </div>

                {/* Main Content */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* SLAM Map */}
                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <MapPin className="w-5 h-5" />
                        SLAM Map & Path
                      </CardTitle>
                      <CardDescription>Real-time mapping with vehicle path</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <canvas
                        ref={canvasRef}
                        width={400}
                        height={300}
                        className="border border-gray-600 rounded w-full bg-black"
                      />
                      <div className="mt-2 text-sm text-gray-400">
                        Path points: {vehicleData?.map_data.path_history?.length || 0} | Obstacles:{" "}
                        {vehicleData?.map_data.obstacles?.length || 0}
                      </div>
                    </CardContent>
                  </Card>

                  {/* Sensor Data */}
                  <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                    <CardHeader>
                      <CardTitle className="flex items-center gap-2">
                        <Radar className="w-5 h-5" />
                        Ultrasonic Sensors
                      </CardTitle>
                      <CardDescription>Real-time distance measurements</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {["Front", "Left", "Right", "Rear"].map((direction, index) => {
                        const distance = vehicleData?.sensor_data.ultrasonic[index] || 0
                        const isObstacle = distance < 50
                        return (
                          <div key={direction} className="space-y-2">
                            <div className="flex justify-between">
                              <span className="text-sm font-medium">{direction}</span>
                              <span className={`text-sm ${isObstacle ? "text-red-400" : "text-gray-400"}`}>
                                {distance.toFixed(1)} cm
                              </span>
                            </div>
                            <Progress
                              value={(distance / 400) * 100}
                              className={`h-2 ${isObstacle ? "bg-red-900" : ""}`}
                            />
                          </div>
                        )
                      })}
                    </CardContent>
                  </Card>
                </div>
              </>
            ) : (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardContent className="text-center py-12">
                  <p className="text-gray-400 mb-4">No vehicle connected</p>
                  <Button onClick={() => setActiveTab("vehicles")}>Connect to a Vehicle</Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Control Tab */}
          <TabsContent value="control" className="space-y-6">
            {activeVehicle && isConnected ? (
              <>
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader>
                    <CardTitle>Vehicle Control</CardTitle>
                    <CardDescription>Remote control and emergency functions</CardDescription>
                  </CardHeader>
                  <CardContent className="flex gap-4">
                    <Button
                      onClick={() => sendVehicleCommand("start")}
                      disabled={isLoading || !isConnected}
                      className="flex items-center gap-2"
                    >
                      <Play className="w-4 h-4" />
                      Start Vehicle
                    </Button>
                    <Button
                      onClick={() => sendVehicleCommand("stop")}
                      disabled={isLoading || !isConnected}
                      variant="outline"
                      className="flex items-center gap-2"
                    >
                      <Square className="w-4 h-4" />
                      Stop Vehicle
                    </Button>
                    <Button
                      onClick={() => sendVehicleCommand("emergency_stop")}
                      disabled={isLoading || !isConnected}
                      variant="destructive"
                      className="flex items-center gap-2"
                    >
                      <AlertTriangle className="w-4 h-4" />
                      Emergency Stop
                    </Button>
                  </CardContent>
                </Card>

                {/* Obstacle Detection Status */}
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle
                        className={`w-5 h-5 ${vehicleData?.action_data.obstacle_detected ? "text-red-400" : "text-green-400"}`}
                      />
                      Obstacle Detection & Navigation
                    </CardTitle>
                    <CardDescription>AI decision making and sensor fusion</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="space-y-2">
                        <h4 className="font-medium">Current Decision</h4>
                        <div className="text-2xl font-bold text-blue-400">
                          {vehicleData?.action_data.action?.toUpperCase() || "N/A"}
                        </div>
                        <Progress value={(vehicleData?.action_data.action_confidence || 0) * 100} className="h-2" />
                        <p className="text-xs text-gray-400">
                          Confidence: {((vehicleData?.action_data.action_confidence || 0) * 100).toFixed(1)}%
                        </p>
                      </div>

                      <div className="space-y-2">
                        <h4 className="font-medium">Speed Control</h4>
                        <div className="text-2xl font-bold text-green-400">
                          {((vehicleData?.action_data.speed || 0) * 100).toFixed(0)}%
                        </div>
                        <Progress value={(vehicleData?.action_data.speed || 0) * 100} className="h-2" />
                        <p className="text-xs text-gray-400">Motor Speed</p>
                      </div>

                      <div className="space-y-2">
                        <h4 className="font-medium">Obstacle Status</h4>
                        <div
                          className={`text-2xl font-bold ${vehicleData?.action_data.obstacle_detected ? "text-red-400" : "text-green-400"}`}
                        >
                          {vehicleData?.action_data.obstacle_detected ? "DETECTED" : "CLEAR"}
                        </div>
                        <Progress value={(vehicleData?.action_data.obstacle_confidence || 0) * 100} className="h-2" />
                        <p className="text-xs text-gray-400">
                          Confidence: {((vehicleData?.action_data.obstacle_confidence || 0) * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardContent className="text-center py-12">
                  <p className="text-gray-400 mb-4">No vehicle connected</p>
                  <Button onClick={() => setActiveTab("vehicles")}>Connect to a Vehicle</Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* System Tab */}
          <TabsContent value="system" className="space-y-6">
            {activeVehicle && isConnected && systemInfo ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
                    <Cpu className="h-4 w-4 text-orange-400" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-orange-400">{systemInfo.cpu.percent.toFixed(1)}%</div>
                    <Progress value={systemInfo.cpu.percent} className="mt-2" />
                    <p className="text-xs text-gray-400 mt-1">
                      {systemInfo.cpu.count} cores |{" "}
                      {systemInfo.cpu.temperature ? `${systemInfo.cpu.temperature.toFixed(1)}°C` : "N/A"}
                    </p>
                  </CardContent>
                </Card>

                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Memory</CardTitle>
                    <HardDrive className="h-4 w-4 text-cyan-400" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-cyan-400">{systemInfo.memory.percent.toFixed(1)}%</div>
                    <Progress value={systemInfo.memory.percent} className="mt-2" />
                    <p className="text-xs text-gray-400 mt-1">
                      {formatBytes(systemInfo.memory.used)} / {formatBytes(systemInfo.memory.total)}
                    </p>
                  </CardContent>
                </Card>

                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
                    <HardDrive className="h-4 w-4 text-purple-400" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-purple-400">{systemInfo.disk.percent.toFixed(1)}%</div>
                    <Progress value={systemInfo.disk.percent} className="mt-2" />
                    <p className="text-xs text-gray-400 mt-1">{formatBytes(systemInfo.disk.free)} free</p>
                  </CardContent>
                </Card>

                <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-sm font-medium">Uptime</CardTitle>
                    <Activity className="h-4 w-4 text-green-400" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-400">{formatUptime(systemInfo.uptime)}</div>
                    <p className="text-xs text-gray-400 mt-1">
                      {systemInfo.hostname} | {systemInfo.bluetooth_clients} BT clients
                    </p>
                  </CardContent>
                </Card>
              </div>
            ) : (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardContent className="text-center py-12">
                  <p className="text-gray-400 mb-4">No vehicle connected</p>
                  <Button onClick={() => setActiveTab("vehicles")}>Connect to a Vehicle</Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* Logs Tab */}
          <TabsContent value="logs" className="space-y-6">
            {activeVehicle && isConnected ? (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    System Logs
                  </CardTitle>
                  <CardDescription>Real-time system and vehicle logs</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="bg-black rounded-lg p-4 h-96 overflow-y-auto font-mono text-sm">
                    {logs.map((log, index) => (
                      <div key={index} className="text-green-400 mb-1">
                        {log}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="bg-gray-800/50 border-gray-700 backdrop-blur">
                <CardContent className="text-center py-12">
                  <p className="text-gray-400 mb-4">No vehicle connected</p>
                  <Button onClick={() => setActiveTab("vehicles")}>Connect to a Vehicle</Button>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>

        {/* Add Vehicle Dialog */}
        <Dialog open={showVehicleDialog} onOpenChange={setShowVehicleDialog}>
          <DialogContent className="sm:max-w-md bg-gray-800 border-gray-700">
            <DialogHeader>
              <DialogTitle className="text-white">Add New Vehicle</DialogTitle>
              <DialogDescription className="text-gray-400">
                Enter the vehicle details to add it to your dashboard
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="vehicle-name" className="text-white">
                  Vehicle Name
                </Label>
                <Input
                  id="vehicle-name"
                  value={newVehicleForm.name}
                  onChange={(e) => setNewVehicleForm({ ...newVehicleForm, name: e.target.value })}
                  className="bg-gray-700 border-gray-600 text-white"
                  placeholder="e.g., Mining Vehicle #1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="vehicle-url" className="text-white">
                  Server URL
                </Label>
                <Input
                  id="vehicle-url"
                  value={newVehicleForm.url}
                  onChange={(e) => setNewVehicleForm({ ...newVehicleForm, url: e.target.value })}
                  className="bg-gray-700 border-gray-600 text-white"
                  placeholder="http://192.168.1.100:5000"
                />
              </div>
              <div className="flex gap-2">
                <Button onClick={addVehicle} className="flex-1">
                  Add Vehicle
                </Button>
                <Button onClick={() => setShowVehicleDialog(false)} variant="outline" className="flex-1">
                  Cancel
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
